# The MIT License (MIT)
# Copyright (c) 2022 by the xcube team and contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import json
from functools import cached_property
from itertools import filterfalse
from string import Template
from typing import Optional, Mapping, Dict, Any, Set, Union

import jwt
import jwt.algorithms
import requests

from xcube.server.api import ApiContext
from xcube.server.api import ApiError
from .config import AuthConfig


class AuthContext(ApiContext):

    @cached_property
    def auth_config(self) -> Optional[AuthConfig]:
        return AuthConfig.from_config(self.config)

    @property
    def can_authenticate(self) -> bool:
        """Test whether the user can authenticate.
        Even if authentication service is configured, user authentication
        may still be optional. In this case the server will publish
        the resources configured to be free for everyone.
        """
        return self.auth_config is not None

    @property
    def must_authenticate(self) -> bool:
        """
        Test whether the user must authenticate.
        """
        return self.auth_config is not None and self.auth_config.is_required

    @cached_property
    def jwks(self) -> Dict[str, Any]:
        response = requests.get(self.auth_config.well_known_jwks)
        return json.loads(response.content)

    @cached_property
    def jwks(self):
        assert self.auth_config is not None
        jwks_uri = self.auth_config.well_known_jwks
        openid_config_uri = self.auth_config.well_known_oid_config
        response = requests.get(openid_config_uri)
        if response.ok:
            openid_config = json.loads(response.content)
            if openid_config and 'jwks_uri' in openid_config:
                jwks_uri = openid_config['jwks_uri']
        response = requests.get(jwks_uri)
        if response.ok:
            return json.loads(response.content)
        # TODO (forman): convert into ApiError
        response.raise_for_status()

    def get_granted_scopes(self, request_headers: Mapping[str, str]) \
            -> Optional[Set[str]]:
        must_authenticate = self.must_authenticate
        id_token = self.get_id_token(request_headers,
                                     require_auth=must_authenticate)
        permissions = None
        if id_token:
            permissions = id_token.get('permissions')
            if not isinstance(permissions, (list, tuple)):
                scope = id_token.get('scope')
                if isinstance(scope, str):
                    permissions = scope.split(' ')
            if permissions is not None:
                permissions = self._interpolate_permissions(id_token,
                                                            permissions)
        return permissions

    def get_id_token(self,
                     request_headers: Mapping[str, str],
                     require_auth: bool = False) \
            -> Optional[Mapping[str, str]]:
        """Decode the access token and verifies it."""

        access_token = self.get_access_token(request_headers,
                                             require_auth=require_auth)
        if access_token is None:
            return None

        auth_config = self.auth_config
        if auth_config is None:
            # Ignore access token
            return None

        # With auth_config and access_token, we expect authorization
        # to work. From here on we raise, if anything fails.

        # Get the unverified header of the access token
        try:
            unverified_header = jwt.get_unverified_header(access_token)
        except jwt.InvalidTokenError:
            unverified_header = None
        if not unverified_header \
                or not unverified_header.get("kid") \
                or not unverified_header.get("alg"):
            # "alg" should be "RS256" or "HS256" or others
            raise ApiError.BadRequest(
                "Invalid header."
                " A signed JWT Access Token is expected."
            )

        # The key identifier of the access token which we must validate.
        access_token_kid = unverified_header["kid"]

        # Get JSON Web Token (JWK) Keys
        jwks = self.jwks

        # Find access_token_kid in JWKS to obtain rsa_key
        rsa_key = None
        for key in jwks["keys"]:
            if key["kid"] == access_token_kid:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break
        if rsa_key is None:
            raise ApiError.BadRequest(
                "Invalid header. Unable to find appropriate key in JWKS."
            )

        # Now we are ready to decode the access token
        try:
            id_token = jwt.decode(
                access_token,
                jwt.algorithms.RSAAlgorithm.from_jwk(rsa_key),
                issuer=auth_config.authority,
                audience=auth_config.audience,
                algorithms=auth_config.algorithms
            )
        except jwt.PyJWTError as e:
            raise ApiError.BadRequest(
                f"Failed to decode access token: {e}"
            ) from e

        return id_token

    @classmethod
    def get_access_token(cls,
                         request_headers: Mapping[str, str],
                         require_auth: bool = False) -> Optional[str]:
        """Obtain the access token from the Authorization Header
        """
        # noinspection PyUnresolvedReferences
        auth = request_headers.get("Authorization", None)
        if not auth:
            if require_auth:
                raise ApiError.Unauthorized(
                    "Authorization header is expected."
                )
            return None

        parts = auth.split()

        if parts[0].lower() != "bearer":
            raise ApiError.BadRequest(
                'Invalid header.'
                ' Authorization header must start with "Bearer".'
            )
        elif len(parts) == 1:
            raise ApiError.BadRequest(
                "Invalid header."
                " Bearer token not found."
            )
        elif len(parts) > 2:
            raise ApiError.BadRequest(
                "Invalid header."
                " Authorization header must be Bearer token."
            )

        return parts[1]

    def _interpolate_permissions(self,
                                 id_token: Mapping[str, Any],
                                 permissions: Union[list, tuple]):
        predicate = self._is_template_permission

        plain_permissions = set(filterfalse(predicate, permissions))
        if len(plain_permissions) == len(permissions):
            return plain_permissions

        templ_permissions = filter(predicate, permissions)
        id_mapping = self._get_template_dict(id_token)
        return plain_permissions.union(
            set(Template(permission).safe_substitute(id_mapping)
                for permission in templ_permissions)
        )

    @staticmethod
    def _is_template_permission(permission: str) -> bool:
        return '$' in permission

    @staticmethod
    def _get_template_dict(id_token: Mapping[str, Any]) -> Dict[str, str]:
        d = {k: v
             for k, v in id_token.items()
             if isinstance(v, str)}
        if 'username' not in d and 'preferred_username' in d:
            d['username'] = d['preferred_username']
        return d
