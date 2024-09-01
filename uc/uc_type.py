class uCType:
    """
    Class that represents a type in the uC language.  Basic
    Types are declared as singleton instances of this type.
    """
    def __init__(self, name, binary_ops=set(), unary_ops=set(),
                 rel_ops=set(), assign_ops=set()):
        """
        You must implement yourself and figure out what to store.
        """
        self.typename = name
        self.unary_ops = unary_ops
        self.binary_ops = binary_ops
        self.rel_ops = rel_ops
        self.assign_ops = assign_ops

# Create specific instances of basic types. You will need to add
# appropriate arguments depending on your definition of uCType
IntType = uCType("int",
                 unary_ops={"-", "+", "*", "&", "++", "--"},
                 binary_ops={"+", "-", "*", "/", "%"},
                 rel_ops={"==", "!=", "<", ">", "<=", ">="},
                 assign_ops={"=", "+=", "-=", "*=", "/=", "%="},
)

# TODO: add other basic types
# CharType = uCType("char", ...)
CharType = uCType("char",
                  # TODO: Complete
                  unary_ops={"-", "+", "*", "&", "++", "--"},
                  binary_ops={},
                  rel_ops = {"==", "!="},
                  assign_ops={"="},
)

FloatType = uCType("float",
                   unary_ops={"-", "+", "*", "&", "++", "--"},
                   binary_ops={"+", "-", "*", "/", "%"},
                   rel_ops={"==", "!=", "<", ">", "<=", ">="},
                   assign_ops={"=", "+=", "-=", "*=", "/=", "%="},
)

BoolType = uCType("bool",
                  unary_ops={"!", "&", "*"},
                  binary_ops={"&&", "||"},
                  rel_ops={"==", "!="},
                  assign_ops={"="},
)

VoidType = uCType("void")

StringType = uCType("string",
                    binary_ops={"+"},
                    rel_ops={"==", "!="},
                    assign_ops={"=", "+="},
)

class ArrayType(uCType):
    def __init__(self, element_type, size=None):
        """
        type: Any of the uCTypes can be used as the array's type. This
              means that there's support for nested types, like matrices.
        size: Integer with the length of the array.
        """
        self.type = element_type
        self.size = size
        super().__init__(None, rel_ops={"==", "!="}, unary_ops={"*", "&"})

class FunctionType(uCType):
    def __init__(self, type, params):
        """
        type: Any of the uCTypes can be used as the array's type. This
              means that there's support for nested types, like matrices.
        params: function parameters.
        """
        self.type = type
        self.params = params
        super().__init__(None)
    
    def __str__(self):
        return ('type(' + self.type.type.name + ')')
    
