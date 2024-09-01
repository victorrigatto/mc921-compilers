import argparse
import pathlib
import sys
from copy import deepcopy
from typing import Any, Dict, Union
from uc.uc_ast import *
from uc.uc_parser import UCParser
from uc.uc_type import *


class SymbolTable:
    """Class representing a symbol table.

    `add` and `lookup` methods are given, however you still need to find a way to 
    deal with scopes.

    ## Attributes
    - :attr data: the content of the SymbolTable
    """

    def __init__(self) -> None:
        """ Initializes the SymbolTable. """
        self.__data = dict()

    @property
    def data(self) -> Dict[str, Any]:
        """ Returns a copy of the SymbolTable.
        """
        return deepcopy(self.__data)

    def add(self, name: str, value: Any, scope) -> None:
        """ Adds to the SymbolTable.

        ## Parameters
        - :param name: the identifier on the SymbolTable
        - :param value: the value to assign to the given `name`
        """
        self.__data[(name, scope)] = value

    def lookup(self, name: str, scope) -> Union[Any, None]:
        """ Searches `name` on the SymbolTable and returns the value
        assigned to it.

        ## Parameters
        - :param name: the identifier that will be searched on the SymbolTable

        ## Return
        - :return: the value assigned to `name` on the SymbolTable. If `name` is not found, `None` is returned.
        """
        return self.__data.get((name, scope), None)


class NodeVisitor:
    """A base NodeVisitor class for visiting uc_ast nodes.
    Subclass it and define your own visit_XXX methods, where
    XXX is the class name you want to visit with these
    methods.
    """

    _method_cache = None

    def visit(self, node):
        """Visit a node."""

        if self._method_cache is None:
            self._method_cache = {}

        visitor = self._method_cache.get(node.__class__.__name__)
        if visitor is None:
            method = "visit_" + node.__class__.__name__
            visitor = getattr(self, method, self.generic_visit)
            self._method_cache[node.__class__.__name__] = visitor

        return visitor(node)

    def generic_visit(self, node):
        """Called if no explicit visitor function exists for a
        node. Implements preorder visiting of the node.
        """
        for _, child in node.children():
            self.visit(child)


class Visitor(NodeVisitor):
    """
    Program visitor class. This class uses the visitor pattern. You need to define methods
    of the form visit_NodeName() for each kind of AST node that you want to process.
    """

    def __init__(self):
        # Initialize the symbol table
        self.symtab = SymbolTable()
        self.typemap = {
            "int": IntType,
            "char": CharType,
            # TODO
            "float": FloatType,
            "string": StringType,
            "void": VoidType,
            "bool": BoolType,
        }
        # Scope management
        self.aux = 0
        self.aux_citens = 0
        self.aux_counter = 0
        self.scope = 0
        self.isLocal = 0
        self.isGlobal = 0

    def _assert_semantic(self, condition: bool, msg_code: int, coord, name: str = "", ltype="", rtype=""):
        """Check condition, if false print selected error message and exit"""
        error_msgs = {
            1: f"{name} is not defined",
            2: f"subscript must be of type(int), not {ltype}",
            3: "Expression must be of type(bool)",
            4: f"Cannot assign {rtype} to {ltype}",
            5: f"Binary operator {name} does not have matching LHS/RHS types",
            6: f"Binary operator {name} is not supported by {ltype}",
            7: "Break statement must be inside a loop",
            8: "Array dimension mismatch",
            9: f"Size mismatch on {name} initialization",
            10: f"{name} initialization type mismatch",
            11: f"{name} initialization must be a single element",
            12: "Lists have different sizes",
            13: "List & variable have different sizes",
            14: f"conditional expression is {ltype}, not type(bool)",
            15: f"{name} is not a function",
            16: f"no. arguments to call {name} function mismatch",
            17: f"Type mismatch with parameter {name}",
            18: "The condition expression must be of type(bool)",
            19: "Expression must be a constant",
            20: "Expression is not of basic type",
            21: f"{name} does not reference a variable of basic type",
            22: f"{name} is not a variable",
            23: f"Return of {ltype} is incompatible with {rtype} function definition",
            24: f"Name {name} is already defined in this scope",
            25: f"Unary operator {name} is not supported",
        }
        if not condition:
            msg = error_msgs[msg_code]  # invalid msg_code raises Exception
            print("SemanticError: %s %s" % (msg, coord), file=sys.stdout)
            sys.exit(1)

    ################################################################
    # Program ok
    # BinaryOp ok
    # Assignment ok
    # FuncDef ok
    # ParamList ok
    # GlobalDecl ok
    # Decl ok
    # VarDecl ok
    # ArrayDecl ok
    # FuncDecl ok
    # DeclList ok
    # Type ok
    # If ok
    # For ok
    # While ok
    # Compound ok
    # Break ok
    # FuncCall ok
    # Assert ok
    # EmptyStatement ok
    # Print ok
    # Return ok
    # Constant ok
    # ID ok
    # UnaryOp ok
    # ExprList ok
    # ArrayRef ok
    # InitList ok
    ################################################################

    def visit_Program(self, node):
        #print(node)
        # Visit all of the global declarations
        for _decl in node.gdecls:
            self.visit(_decl)

    def visit_BinaryOp(self, node):
        #print(node)
        # Visit the left and right expression
        ltype = self.visit(node.lvalue)
        rtype = self.visit(node.rvalue)
        # - Make sure left and right operands have the same type
        self._assert_semantic(ltype==rtype, 5, node.coord, name=node.op)
        # - Make sure the operation is supported
        self._assert_semantic(node.op in ltype.rel_ops or node.op in ltype.binary_ops, 6, node.coord, name=node.op, ltype=('type(' + ltype.typename + ')'))
        # - Assign the result type
        if (node.op in ltype.rel_ops):
            node.type = BoolType
            return BoolType
        else:
            node.type = ltype
            return node.type

    def visit_Assignment(self, node):
        #print(node)
        # visit right side
        rtype = self.visit(node.rvalue)
        # visit left side (must be a location)
        _var = self.visit(node.lvalue)
        if isinstance(_var, ID):
            self._assert_semantic(_var.scope is not None, 1, node.coord, name = _var.name)
        # Check that assignment is allowed
        ltype = _var
        self._assert_semantic(ltype == rtype, 4, node.coord, ltype = ltype, rtype = rtype)
        # Check that assign_ops is supported by the type
        self._assert_semantic(node.op in ltype.assign_ops, 5, node.coord, name = node.op, ltype = ltype)

    def visit_FuncDef(self, node):
        #print(node)

        aux_citens = 0

        self.visit(node.decl)
        self.visit(node.body)

        if (node.body.citens is not None):
            while (aux_citens < len(node.body.citens)):
                #print(node.body.citens[aux_citens])
                aux_citen = (node.body.citens[aux_citens])
                if (type(aux_citen) is not Return):
                    pass
                else:
                    ltype = ('type(' + self.visit(aux_citen).typename + ')')
                    rtype = ('type(' + node.type.name + ')')
                    tname = self.visit(aux_citen).typename
                    if (tname == node.type.name):
                        self._assert_semantic(True, 23, aux_citen.coord, ltype = ltype, rtype = rtype)
                    else:
                        self._assert_semantic(False, 23, aux_citen.coord, ltype = ltype, rtype = rtype)
                aux_citens += 1

        else: #then void
            ltype = (('type(void)'))
            rtype = (('type(' + node.type.name + ')'))
            if (node.type.name == 'void'):
                self._assert_semantic(True, 23, node.body.coord, ltype = ltype, rtype = rtype)
            else:
                self._assert_semantic(False, 23, node.body.coord, ltype = ltype, rtype = rtype)

    def visit_ParamList(self, node):
        # Just visit.
        for param in (node.params):
            self.visit(param)

    def visit_GlobalDecl(self, node):
        #print(node)
        for _decl in (node.decls):
            self.visit(_decl)

    def visit_Decl(self, node):
        expr_counter = 0
        #print(node)
        #print(self.isGlobal)
        #print(self.isLocal)
        if (type(node.type) is not None and type(node.type) is not ArrayDecl):
            vtype = self.visit(node.type)
            if (node.init is not None):
                if (type(node.init) is not InitList):
                    self._assert_semantic(True, 11, node.name.coord, name = node.name.name)
                else:
                    self._assert_semantic(False, 11, node.name.coord, name = node.name.name)
                
                if (type(node.init) is not Constant):
                    self.visit(node.init)
                else:
                    if (node.init.type is vtype.typename): 
                        self._assert_semantic(True, 10, node.name.coord, name = node.name.name)
                    else:
                        self._assert_semantic(False, 10, node.name.coord, name = node.name.name)  
            if (self.isLocal == 0):
                if ((self.symtab.lookup(node.name.name, self.isGlobal)) is not None):
                    self._assert_semantic(False, 24, node.name.coord, name = node.name.name)
        else:
            #print(node)
            (vtype, dim) = self.visit(node.type)
            if (node.init is not None):
                if (type(node.init) is ID):
                    self.visit(node.init)
                elif (type(node.init) is not Constant):
                    if (dim[0] is not None):
                        if (len(node.init.exprs) is dim[0]):
                            self._assert_semantic(True, 13, node.name.coord)
                        else:
                            self._assert_semantic(False, 13, node.name.coord)
                        while (expr_counter < len(node.init.exprs)):
                            #print(node.init.exprs)
                            if (type(node.init.exprs[expr_counter]) is not Constant):
                                self._assert_semantic(False, 19, node.init.exprs[expr_counter].coord)
                            else:
                                self._assert_semantic(True, 19, node.init.exprs[expr_counter].coord)

                            if (node.init.exprs[expr_counter].type is not (vtype.typename)):
                                self._assert_semantic(False, 11, node.name.coord, name = node.name.name)
                            else:
                                self._assert_semantic(True, 11, node.name.coord, name = node.name.name)
                            expr_counter += 1
                        #print(expr_counter)
                    else:
                        dim[0] = len(node.init.exprs)
                    
                else: 
                    if (node.init.type == 'string'):
                        if (vtype.typename == 'char'):
                            self._assert_semantic(True, 10, node.name.coord, name = node.name.name)
                        else:
                            self._assert_semantic(False, 10, node.name.coord, name = node.name.name)
                        if (len(node.init.value) is dim[0]):
                            self._assert_semantic(True, 9, node.name.coord, name = node.name.name)
                        else:
                            self._assert_semantic(False, 9, node.name.coord, name = node.name.name)
            
            elif (len(dim) >= 1):
                #print(len(dim))
                if (dim[0] is None):
                    self._assert_semantic(False, 8, node.name.coord)
                else:
                    self._assert_semantic(True, 8, node.name.coord)
                    
            if (self.symtab.lookup(node.name.name, self.isGlobal) is None):
                self._assert_semantic(True, 24, node.name.coord, name = node.name.name)
            else:
                self._assert_semantic(False, 24, node.name.coord, name = node.name.name)
          
            #print(vtype)
            #print(node.type.type)
            vtype = (ArrayType(node.type.type, dim))
            node.type.dim = dim[0]
                
        if (self.isLocal == 0):
            self.symtab.add(node.name.name, vtype, self.isGlobal)
        else:
            self.symtab.add(node.name.name, vtype, self.isLocal)

    def visit_VarDecl(self, node):
        #print(node)
        self.visit(node.type)

        return (self.typemap[node.type.name])

    def visit_ArrayDecl(self, node):
        #print(node)
        dim = []

        if ((type(node.type) is not VarDecl)):
            (vtype, dim) = self.visit(node.type)
        elif ((type(node.type) is VarDecl)):
            vtype = self.visit(node.type)
        if (node.dim is not None):
            dim.append(node.dim.value)
        elif (node.dim is None):
            dim.append(node.dim)

        return (vtype, dim)
    
    def visit_FuncDecl(self, node):
        #print(node)
        self.isGlobal = (self.isGlobal + 1)
        self.visit(node.type)
        if (node.args is not None):
            for arg in (node.args):
                self.visit(arg)
                
        return FunctionType(node.type, node.args)
    
    def visit_DeclList(self, node):
        #print(node)
        if (node.decls is not None):
            for decl in (node.decls):
                self.visit(decl)

    def visit_Type(self, node):
        # Just visit
        pass

    def visit_If(self, node):
        #print(node)
        self.visit(node.iftrue)
        self.visit(node.cond)
        if (node.iffalse is not None):
            self.visit(node.iffalse)
        if (type(node.cond) is ID):
            self._assert_semantic(False, 18, node.cond.coord)
        elif (type(node.cond) is Constant):
            self._assert_semantic(False, 18, node.cond.coord)
        elif (type(node.cond) is Assignment):
            self._assert_semantic(False, 18, node.cond.coord)
        elif (type(node.cond) is BinaryOp):
            self._assert_semantic(True, 18, node.cond.coord)
        elif (type(node.cond) is UnaryOp):
            self._assert_semantic((node.cond.op in BoolType.unary_ops), 18, node.cond.coord)

    def visit_For(self, node):
        #print(node)
        vtype = node.init
        self.isLocal = (self.isGlobal + 1)

        if (type(vtype) is Assignment):
            self.visit(vtype)
        else:
            for decl in (vtype.decls):
                #aux2 = (aux2 + 1)
                vtype = self.visit(decl.type)
                self.symtab.add(decl.name.name, vtype, self.isLocal)
            #print(aux2)
        #Visit the rest of the for
        self.visit(node.cond)

        self.visit(node.body)

        self.visit(node.next)

        self.isLocal = 0
        
    def visit_While(self, node):
        #print(node)
        vtype = self.visit(node.cond)

        self.aux = (self.aux + 1)
        #print(node.cond)
        #Check if ID
        if (type(node.cond) is ID):
            ltype = ('type(' + node.cond.type + ')')
            if (vtype is BoolType):
                self._assert_semantic(True, 14, node.coord, ltype = ltype)
            else:
                self._assert_semantic(False, 14, node.coord, ltype = ltype)
        #Check if Constant
        elif (type(node.cond) is Constant):
            ltype = ('type(' + node.cond.type + ')')
            if (node.cond.type == 'bool'):
                self._assert_semantic(True, 14, node.coord, ltype = ltype)
            else:
                self._assert_semantic(False, 14, node.coord, ltype = ltype)
        #Check if Binary
        elif (type(node.cond) is BinaryOp):
            if (vtype is BoolType):
                self._assert_semantic(True, 14, node.coord, ltype = vtype)
            else:
                self._assert_semantic(False, 14, node.coord, ltype = vtype)
        #Else it must be Unary
        else:
            self._assert_semantic((node.cond.op in BoolType.unary_ops), 14, node.coord, ltype = vtype)

        self.visit(node.body)

    def visit_Compound(self, node):
        #print(node)
        if (node.citens):
            for citens in (node.citens):
                self.visit(citens)

    def visit_Break(self, node):
        #print(node)
        if (self.isLocal):
            self._assert_semantic(True, 7, node.coord)
        else:
            self._assert_semantic(False, 7, node.coord)

    def visit_FuncCall(self, node):
        #print(node)

        scope_counter = 0
        expr_counter = 0
        self.aux = (self.aux + 1)

        while (scope_counter <= self.isGlobal):
            if (self.symtab.lookup(node.name.name, scope_counter) is None):
                pass
            else:
                break
            scope_counter += 1
        #print(scope_counter)
        if (type(self.symtab.lookup(node.name.name, scope_counter)) is not FunctionType):
            self._assert_semantic(False, 15, node.coord, name = node.name.name)
        else:
            self._assert_semantic(True, 15, node.coord, name = node.name.name)

        if (self.symtab.lookup(node.name.name, scope_counter).params is None):
            if (self.symtab.lookup(node.name.name, scope_counter) is None):
                pass
            else:
                self._assert_semantic(True, 1, node.coord, name = node.name.name)
        else:
            #print(node.args)
            #print(self.isGlobal)
            if (type(node.args) is not ExprList):
                if (type(node.args) is not BinaryOp):
                    if (type(node.args) is not Constant):
                        if (self.isLocal):
                            aux_argtype = (self.symtab.lookup(node.args.name, self.isLocal))
                            if (aux_argtype is None):
                                aux_argtype = (self.symtab.lookup(node.args.name, self.isGlobal))
                        else:
                            aux_argtype = self.symtab.lookup(node.args.name, self.isGlobal)
                        if (aux_argtype is None):
                            aux_argtype = self.symtab.lookup(node.args.name, 0)
                        node.args.type = aux_argtype
                        aux_argtype = aux_argtype.typename
                    else:
                        aux_argtype = node.args.type
                else:
                    aux_argtype = (self.visit(node.args).typename)

                if (aux_argtype == self.symtab.lookup(node.name.name, scope_counter).params.params[0].type.type.name):
                    self._assert_semantic(True, 17, node.args.coord, name = self.symtab.lookup(node.name.name, scope_counter).params.params[0].name.name)
                else:
                    self._assert_semantic(False, 17, node.args.coord, name = self.symtab.lookup(node.name.name, scope_counter).params.params[0].name.name)

                if (len(self.symtab.lookup(node.name.name, scope_counter).params.params) == 1):
                    self._assert_semantic(True, 16, node.coord, node.name.name)
                else:
                    self._assert_semantic(False, 16, node.coord, node.name.name)
            else:
                if (len(node.args.exprs) is len(self.symtab.lookup(node.name.name, scope_counter).params.params)):
                    self._assert_semantic(True, 16, node.coord, node.name.name)
                else:
                    self._assert_semantic(False, 16, node.coord, node.name.name)
                
                while (expr_counter < len(node.args.exprs)):
                    if (type(node.args.exprs[expr_counter]) is Constant):
                        aux_argtype = (node.args.exprs[expr_counter].type)
                    elif (type(node.args.exprs[expr_counter]) is BinaryOp):
                        aux_argtype = (self.visit(node.args.exprs[expr_counter]).typename)
                    else:
                        if (self.isLocal):
                            aux_argtype = (self.symtab.lookup(node.args.exprs[expr_counter].name, self.isLocal))
                            if (aux_argtype is None):
                                aux_argtype = (self.symtab.lookup(node.args.exprs[expr_counter].name, self.isGlobal))
                        else:
                            aux_argtype = (self.symtab.lookup(node.args.exprs[expr_counter].name, self.isGlobal))
                        if (aux_argtype is None):
                            aux_argtype = (self.symtab.lookup(node.args.exprs[expr_counter].name, 0))
                        node.args.exprs[expr_counter].type = aux_argtype
                        aux_argtype = (aux_argtype.typename)
                    if (aux_argtype == self.symtab.lookup(node.name.name, scope_counter).params.params[expr_counter].type.type.name):
                        self._assert_semantic(True, 17, node.args.exprs[expr_counter].coord, name = self.symtab.lookup(node.name.name, scope_counter).params.params[expr_counter].name.name)
                    else:
                        self._assert_semantic(False, 17, node.args.exprs[expr_counter].coord, name = self.symtab.lookup(node.name.name, scope_counter).params.params[expr_counter].name.name)
                    expr_counter += 1
                #print(expr_counter)
        
        node.name.type = (self.symtab.lookup(node.name.name, scope_counter).type.type.name)
        
        return (self.typemap[node.name.type])

    def visit_Assert(self, node):
        #print(node)
        vtype = self.visit(node.expr)
        if (vtype == BoolType):
            self._assert_semantic(True, 3, node.expr.coord)
        else:
            self._assert_semantic(False, 3, node.expr.coord)

    def visit_EmptyStatement(self, node):
        # Do nothing
        pass

    def visit_Print(self, node):
        #print(node)
        #print(self.isLocal)
        #print(self.isGlobal)
        if (node.expr is not None):
            vtype = self.visit(node.expr)
            if (type(node.expr) is not ID):
                if (vtype is not VoidType):
                    if (type(vtype) is not FunctionType):
                        if (type(vtype) is not ArrayType):
                            self._assert_semantic(True, 20, node.expr.coord)
                else:
                    self._assert_semantic(False, 20, node.expr.coord)
            else:
                #print(node)
                if (self.isLocal):
                    vtype = self.symtab.lookup(node.expr.name, self.isLocal)
                    if (vtype is None):
                        vtype = self.symtab.lookup(node.expr.name, self.isGlobal)
                else:
                    vtype = self.symtab.lookup(node.expr.name, self.isGlobal)
                if (vtype is None):
                    vtype = self.symtab.lookup(node.expr.name, 0)
                if (vtype is not VoidType):
                    if (type(vtype) is not FunctionType):
                        if (type(vtype) is not ArrayType):   
                            self._assert_semantic(True, 21, node.expr.coord, name = node.expr.name)
                        else:
                            self._assert_semantic(False, 21, node.expr.coord, name = node.expr.name)            
        else:
            pass        

    def visit_Return(self, node):
        #print(node)
        if (node.expr is None):
            return VoidType
        else:
            return self.visit(node.expr)
    
    def visit_Constant(self, node):
        #print(node)
        return self.typemap[node.type]

    def visit_ID(self, node):
        #print(node)
        #print(self.isLocal)
        #print(self.isGlobal)
        if (self.isLocal):
            node.type = self.symtab.lookup(node.name, self.isLocal)
            if (node.type is None):
                node.type = self.symtab.lookup(node.name, self.isGlobal)
        else:
            node.type = self.symtab.lookup(node.name, self.isGlobal)
        if (node.type is None):
            node.type = self.symtab.lookup(node.name, 0)
        if (node.type is None):
            self._assert_semantic(False, 1, node.coord, node.name)
        else:
            self._assert_semantic(True, 1, node.coord, node.name)

        return node.type

    def visit_UnaryOp(self, node):
        #print(node)
        vtype = self.visit(node.expr)
        self._assert_semantic(node.op in vtype.unary_ops, 25, node.coord, node.op)
        return vtype

    def visit_ExprList(self, node):
        #print(node)
        for expr in (node.exprs):
            self.visit(expr)

    def visit_ArrayRef(self, node):
        #print(node.subscript)
        vtype = self.visit(node.subscript)

        if (vtype is IntType):
            self._assert_semantic(True, 2, node.subscript.coord, ltype = vtype)
        else:
            self._assert_semantic(False, 2, node.subscript.coord, ltype = vtype)

        node.type = self.visit(node.name)
        return vtype
    
    def visit_InitList(self, node):
        #print(node)
        for element in (node.exprs):
            self.visit(element)
            if (type(element) is InitList):
                self._assert_semantic(True, 19, node.coord)
            else:
                self._assert_semantic(False, 19, node.coord)
    
if __name__ == "__main__":
    # create argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input_file", help="Path to file to be semantically checked", type=str
    )
    args = parser.parse_args()

    # get input path
    input_file = args.input_file
    input_path = pathlib.Path(input_file)

    # check if file exists
    if not input_path.exists():
        print("Input", input_path, "not found", file=sys.stderr)
        sys.exit(1)

    # set error function
    p = UCParser()
    # open file and parse it
    with open(input_path) as f:
        ast = p.parse(f.read())
        sema = Visitor()
        sema.visit(ast)
        
