from typing import Callable, Optional, Union, Any, List

from xcube.util.jsonschema import JsonSchema
from xcube.util.jsonschema import JsonObjectSchema

from .info import PyType
from .registry import OpRegistry
from .registry import OP_REGISTRY


def operation(_op: Optional[Callable] = None,
              params_schema: Optional[JsonObjectSchema] = None,
              op_registry: OpRegistry = OP_REGISTRY):
    """Decorator that registers a function as an operation.

    :param _op: the function to register as an operation
    :param params_schema: JSON Schema for the function's parameters
           (a JSON object schema mapping parameter names to their individual
           schemas)
    :param op_registry: the registry in which to register the operation
    :return: the decorated operation, if an operation was supplied;
       otherwise, a decorator function
    """

    def decorator(op: Callable):
        _assert_decorator_target_ok("operation", op)
        op_info = op_registry.register_op(op)
        if params_schema is not None:
            op_info.update_params_schema(params_schema.to_dict())
        return op

    if _op is None:
        return decorator
    else:
        return decorator(_op)


def op_param(name: str,
             json_type: Optional[Union[str, List[str]]] = None,
             py_type: Optional[PyType] = None,
             title: Optional[str] = None,
             description: Optional[str] = None,
             default: Optional[Any] = None,
             required: Optional[bool] = None,
             schema: Optional[JsonSchema] = None,
             op_registry: OpRegistry = OP_REGISTRY):
    """Decorator that adds schema information to the operation parameter given
    by *name*.

    See also
    https://json-schema.org/draft/2020-12/json-schema-validation.html#name-a-vocabulary-for-basic-meta
    :param name: name of the parameter to apply schema information to
    :param json_type: JSON Schema type of the parameter
    :param py_type: Python type of the parameter
    :param title: title of the parameter
    :param description: description of the parameter
    :param default: default value for the parameter
    :param required: whether the parameter is required
    :param schema: JSON Schema describing the parameter
    :param op_registry: registry in which to register the operation
    :return: parameterized decorator for a compute operation function
    """

    def decorator(op: Callable):
        _assert_decorator_target_ok("op_param", op)
        op_info = op_registry.register_op(op)
        op_param_schema = {}
        if schema is not None:
            op_param_schema.update(schema.to_dict())
        if py_type is not None:
            op_info.set_param_py_type(name, py_type)
        if json_type is not None:
            op_param_schema.update({"type": json_type})
        if title is not None:
            op_param_schema.update({"title": title})
        if description is not None:
            op_param_schema.update({"description": description})
        if default is not None:
            op_param_schema.update({"default": default})
        if op_param_schema:
            op_info.update_param_schema(name, op_param_schema)
        if required is not None:
            required_set = set(op_info.params_schema.get("required", []))
            if required and name not in required_set:
                required_set.add(name)
            elif not required and name in required_set:
                required_set.remove(name)
            op_info.update_params_schema({"required": list(required_set)})
        return op

    return decorator


def _assert_decorator_target_ok(decorator_name: str, target: Any):
    if not callable(target):
        raise TypeError(f"decorator {decorator_name!r}"
                        f" can be used with callables only")
