from typing import Any
from inspect import signature

class InputSetMeta(type):
    '''
    Redefine __call__ method to add setattr `input_set` to the instance 
    used to control which parameters are need change.
    
    `input_set` can be modified by `input_set_key_name` parameter in class definition.
    
    eg.
    ```
    class MyClass(metaclass=InputSetMeta, key_name='my_input_set'):
        def __init__(self, **kwargs):
            # do something with my_input_set
            print(self.my_input_set)
    
    >>> A = MyClass(a=1, b=2)
    >>> A.my_input_set
    {'a', 'b'}
    ```
    '''
    def __new__(
        cls, name, bases, namespace, 
        key_name="input_set", 
    ):
        result = type.__new__(cls, name, bases, dict(namespace))
        __input_set_key_name__ = getattr(result, "__input_set_key_name__", None)
        if __input_set_key_name__ is not None:
            if __input_set_key_name__!= key_name:
                raise ValueError("InputSetMeta can only be use same key_name in a class hierarchy.")
        else:
            result.__input_set_key_name__ = key_name
        return result
    def __call__(self, *args: Any, **kwargs: Any):
        sig = signature(self.__class__.__init__)
        input_set = list(kwargs.keys())
        keys = list(sig.parameters.keys())
        l = len(args)
        if l > 0:
            input_set += keys[1:l+1]
        input_set = set(input_set)
        _input_set = getattr(self, self.__input_set_key_name__, None)
        if isinstance(_input_set, property):
            _input_set = _input_set.fget(self)
        if _input_set is not None:
            # merge input_set with previous input_set
            _input_set.update(input_set)
        else:
            setattr(self, self.__input_set_key_name__, input_set)
        return super().__call__(*args, **kwargs)
