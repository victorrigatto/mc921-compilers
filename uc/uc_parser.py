import argparse
import pathlib
import sys
from ply.yacc import yacc
from uc.uc_ast import *
from uc.uc_lexer import UCLexer

class Coord:
    """Coordinates of a syntactic element. Consists of:
    - Line number
    - (optional) column number, for the Lexer
    """

    __slots__ = ("line", "column")

    def __init__(self, line, column=None):
        self.line = line
        self.column = column

    def __str__(self):
        if self.line and self.column is not None:
            coord_str = "@ %s:%s" % (self.line, self.column)
        elif self.line:
            coord_str = "@ %s" % (self.line)
        else:
            coord_str = ""
        return coord_str

class UCParser:

    def __init__(self, debug=True):
        """Create a new uCParser."""
        self.uclex = UCLexer(self._lexer_error)
        self.uclex.build()
        self.tokens = self.uclex.tokens

        self.ucparser = yacc(module=self, start="program", debug=debug)
        # Keeps track of the last token given to yacc (the lookahead token)
        self._last_yielded_token = None

    def parse(self, text, debuglevel=0):
        self.uclex.reset_lineno()
        self._last_yielded_token = None
        return self.ucparser.parse(input=text, lexer=self.uclex, debug=debuglevel)

    def _lexer_error(self, msg, line, column):
        # use stdout to match with the output in the .out test files
        print("LexerError: %s at %d:%d" % (msg, line, column), file=sys.stdout)
        sys.exit(1)

    def _parser_error(self, msg, coord=None):
        # use stdout to match with the output in the .out test files
        if coord is None:
            print("ParserError: %s" % (msg), file=sys.stdout)
        else:
            print("ParserError: %s %s" % (msg, coord), file=sys.stdout)
        sys.exit(1)

    def _token_coord(self, p, token_idx):
        last_cr = p.lexer.lexer.lexdata.rfind("\n", 0, p.lexpos(token_idx))
        if last_cr < 0:
            last_cr = -1
        column = p.lexpos(token_idx) - (last_cr)
        return Coord(p.lineno(token_idx), column)

    def p_program(self, p):
        """ program  : global_declaration_list"""
        # When the 'program' is reduced, it means it found the syntax of a
        # program. This is the ideal place for us to instantiate a Program node.
        p[0] = Program(p[1])
        # Notice that we pass the result of the `global_declaration_kcross`
        # production to the program. Since the gdecls attribute of the Program
        # class expects a list of global declarations, we should expect a list
        # to be returned by the `global_declaration_kcross` semantic action.

    def p_global_declaration_1(self, p):
        """global_declaration : declaration"""
        # Let's apply the same logic as the Program node here
        p[0] = GlobalDecl(p[1])

    def p_global_declaration_2(self, p):
        """global_declaration : function_definition"""
        p[0] = p[1]

    def p_global_declaration_list(self, p):
        """global_declaration_list : global_declaration
        | global_declaration_list global_declaration
        """
        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[2]]

    def p_direct_declarator(self, p):
        """direct_declarator : identifier
        | LPAREN declarator RPAREN
        | direct_declarator LPAREN empty RPAREN
        | direct_declarator LPAREN parameter_list RPAREN
        | direct_declarator LPAREN identifier_list RPAREN
        | direct_declarator LBRACKET empty RBRACKET
        | direct_declarator LBRACKET constant_expression RBRACKET
        """
        identifier = ID(p[1], coord=self._token_coord(p, 1))
        if len(p) == 2:
            p[0] = VarDecl(p[1], None, coord=self._token_coord(p, 1))
        elif len(p) == 4:
            p[0] = p[2]
        else:
            if p[2] == '[':
                array = ArrayDecl(None, p[3] if len(p) > 4 else None, coord=p[1].coord)
                p[0] = self.aux_change_type(decl=p[1], modifier=array)
            else:
                func = FuncDecl(p[3], None, coord=p[1].coord)
                p[0] = self.aux_change_type(decl=p[1], modifier=func)

    def p_expression(self, p):
        """expression  : assignment_expression
        | expression COMMA assignment_expression
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            if not isinstance(p[1], ExprList):
                p[1] = ExprList([p[1]], p[1].coord)
            p[1].exprs.append(p[3])
            p[0] = p[1]

    def p_block_item(self, p):
        """ block_item  : declaration
        | statement
        """
        p[0] = p[1] if isinstance(p[1], list) else [p[1]]

    def p_block_item_list(self, p):
        """ block_item_list : block_item
        | block_item_list block_item
        """
        p[0] = p[1] if len(p) == 2 or p[2] == [None] else p[1] + p[2]

    def p_error(self, p):
        if p:
            self._parser_error(
                "Before %s" % p.value, Coord(p.lineno, self.uclex.find_tok_column(p))
            )
        else:
            self._parser_error("At the end of input (%s)" % self.uclex.filename)

    def p_empty(self, p):
        """empty :"""
        p[0] = None

    def p_declaration(self, p):
        """declaration : decl_body SEMI
        """
        p[0] = p[1]

    def p_init_declarator_list(self, p):
        """init_declarator_list : init_declarator
        | init_declarator_list COMMA init_declarator
        """
        # This is only necessary when we have a list of declarations. Something
        # like 'int a, b, c;'.
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[3]]

    def p_init_declarator(self, p):
        """init_declarator : declarator
        | declarator EQUALS initializer
        """
        # Here is where the Decl node is consolidated. Used dictionaries.
        if len(p) == 2:
            p[0] = dict(decl=p[1], init=None)
        else:
            p[0] = dict(decl=p[1], init=p[3])

    def p_declarator(self, p):
        """declarator : pointer direct_declarator
        | empty direct_declarator
        """
        # This is were it all starts. With modification of type when necessary.
        if p[1] is None:
            p[0] = p[2]
        else:
            p[0] = self.aux_change_type(p[2], p[1])

    def p_identifier(self, p):
        """ identifier : ID """
        p[0] = ID(p[1], coord=self._token_coord(p, 1))

    def p_initializer(self, p):
        """initializer : assignment_expression
        | LBRACE initializer_list RBRACE
        | LBRACE initializer_list COMMA RBRACE
        | LBRACE empty RBRACE
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = p[2]

    def p_binary_expression(self, p):
        """binary_expression : cast_expression
        | binary_expression AND binary_expression
        | binary_expression OR binary_expression
        | binary_expression TIMES binary_expression
        | binary_expression DIVIDE binary_expression
        | binary_expression MOD binary_expression
        | binary_expression PLUS binary_expression
        | binary_expression MINUS binary_expression
        | binary_expression LT binary_expression
        | binary_expression LE binary_expression
        | binary_expression GT binary_expression
        | binary_expression GE binary_expression
        | binary_expression EQ binary_expression
        | binary_expression NE binary_expression
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = BinaryOp(p[2], p[1], p[3], coord=p[1].coord)

    def p_unary_operator(self, p):
        """unary_operator : '&'
        | PLUS
        | MINUS
        | TIMES
        | NOT
        """
        p[0] = p[1]
        
    def p_constant(self, p):
        ''' constant : int_constant
        | char_constant
        | float_constant
        '''
        p[0]= p[1]

    def p_int_constant(self, p):
        """int_constant : INT_CONST
        """
        p[0] = Constant("int", p[1], coord=self._token_coord(p, 1))

    def p_float_constant(self, p):
        """float_constant : FLOAT_CONST
        """
        p[0] = Constant("float", p[1], coord=self._token_coord(p, 1))

    def p_char_constant(self, p):
        """char_constant : CHAR_CONST
        """
        p[0] = Constant("char", p[1], coord=self._token_coord(p, 1))

    def p_string(self, p):
        """string : STRING_LITERAL
        """
        p[0] = Constant("string", p[1], coord=self._token_coord(p, 1))

    def p_iteration_statement(self, p):
        """iteration_statement : WHILE LPAREN expression RPAREN statement
        | FOR LPAREN empty SEMI empty SEMI empty RPAREN statement
        | FOR LPAREN expression SEMI empty SEMI empty RPAREN statement
        | FOR LPAREN expression SEMI expression SEMI empty RPAREN statement
        | FOR LPAREN expression SEMI expression SEMI expression RPAREN statement
        | FOR LPAREN declaration empty SEMI empty RPAREN statement
        | FOR LPAREN declaration expression SEMI empty RPAREN statement
        | FOR LPAREN declaration expression SEMI expression RPAREN statement
        """
        if len(p) == 6:
            p[0] = While(p[3], p[5], coord=self._token_coord(p, 1))
        elif len(p) == 10:
            p[0] = For(p[3], p[5], p[7], p[9], coord=self._token_coord(p, 1))
        else:
            p[0] = For(DeclList(p[3], coord=self._token_coord(p, 1)), p[4], p[6], p[8], coord=self._token_coord(p, 1))

    def p_unary_expression(self, p):
        """unary_expression : postfix_expression
        | PLUSPLUS unary_expression
        | MINUSMINUS unary_expression
        | unary_operator cast_expression
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = UnaryOp(p[1], p[2], coord=p[2].coord)

    def p_statement(self, p):
        """statement : expression_statement
        | compound_statement
        | selection_statement
        | iteration_statement
        | jump_statement
        | assert_statement
        | print_statement
        | read_statement
        """
        p[0] = p[1]

    def p_compound_statement(self, p):
        """compound_statement : LBRACE empty RBRACE
        | LBRACE block_item_list RBRACE
        """
        p[0] = Compound(citens=p[2], coord=self._token_coord(p, 1))

    def p_expression_statement(self, p):
        """expression_statement : empty SEMI
        | expression SEMI
        """
        if p[1] is None:
            p[0] = EmptyStatement(coord=self._token_coord(p, 2))
        else:
            p[0] = p[1]

    def p_read_statement(self, p):
        """read_statement : READ LPAREN argument_expression RPAREN SEMI
        """
        p[0] = Read(p[3], coord=self._token_coord(p, 1))

    def p_print_statement(self, p):
        """print_statement : PRINT LPAREN empty RPAREN SEMI
        | PRINT LPAREN expression RPAREN SEMI
        """
        p[0] = Print(p[3], coord=self._token_coord(p, 1))

    def p_assert_statement(self, p):
        """assert_statement : ASSERT expression SEMI
        """
        p[0] = Assert(p[2], coord=self._token_coord(p, 1))

    def p_selection_statement(self, p):
        """selection_statement : IF LPAREN expression RPAREN statement
        | IF LPAREN expression RPAREN statement ELSE statement
        """
        if len(p) == 6:
            p[0] = If(p[3], p[5], None, coord=self._token_coord(p, 1))
        else:
            p[0] = If(p[3], p[5], p[7], coord=self._token_coord(p, 1))

    def p_function_definition_1(self, p):
        """function_definition : type_specifier declarator declaration_list_emp compound_statement
        """
        p[0] = self.aux_functions(spec=p[1], decl=p[2], param_decls=p[3], statements=p[4])

    def p_function_definition_2(self, p):
        """function_definition : declarator declaration_list_emp compound_statement
        """
        spec = Type('void', coord=self._token_coord(p,1))
        p[0] = self.aux_functions(spec=spec, decl=p[1], param_decls=p[2], statements=p[3])
    
    def p_type_specifier(self, p):
        """type_specifier : VOID
        | CHAR
        | INT
        | FLOAT
        """
        p[0] = Type(p[1], coord=self._token_coord(p, 1))

    def p_pointer(self, p):
        """pointer : '*' pointer
        | '*'
        """
        pass

    def p_identifier_list(self, p):
        """identifier_list : identifier
        | identifier_list COMMA identifier
        """
        if len(p) == 2:
            p[0] = ParamList([p[1]], p[1].coord)
        else:
            p[1].params.append(p[3])
            p[0] = p[1]

    def p_postfix_expression(self, p):
        """postfix_expression : primary_expression
        | postfix_expression LBRACKET expression RBRACKET
        | postfix_expression LPAREN empty RPAREN
        | postfix_expression LPAREN argument_expression RPAREN
        | postfix_expression PLUSPLUS
        | postfix_expression MINUSMINUS
        """
        if len(p) == 2:
            p[0] = p[1]
        elif len(p) == 5:
            if p[2] == '[':
                p[0] = ArrayRef(p[1], p[3], coord=p[1].coord)
            else:
                p[0] = FuncCall(p[1], p[3], coord=p[1].coord)
        else:
            p[0] = UnaryOp('p'+p[2], p[1], coord=p[1].coord)
            
    def p_primary_expression(self, p):
        """primary_expression : identifier
        | constant
        | string
        | LPAREN expression RPAREN
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = p[2]

    def p_constant_expression(self, p):
        """constant_expression : binary_expression
        """
        p[0] = p[1]

    def p_argument_expression(self, p):
        """argument_expression : assignment_expression
        | argument_expression COMMA assignment_expression
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            if not isinstance(p[1], ExprList):
                p[1] = ExprList([p[1]], coord=p[1].coord)
            p[1].exprs.append(p[3])
            p[0] = p[1]

    def p_assignment_expression(self, p):
        """assignment_expression : binary_expression
        | unary_expression assignment_operator assignment_expression
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = Assignment(p[2], p[1], p[3], coord=p[1].coord)

    def p_assignment_operator(self, p):
        """assignment_operator : EQUALS
        | TIMESEQUAL
        | DIVEQUAL
        | MODEQUAL
        | PLUSEQUAL
        | MINUSEQUAL
        """
        p[0] = p[1]

    def p_parameter_list(self, p):
        """parameter_list : parameter_declaration
        | parameter_list COMMA parameter_declaration
        """
        if len(p) == 2:
            p[0] = ParamList([p[1]], coord=p[1].coord)
        else:
            p[1].params.append(p[3])
            p[0] = p[1]

    def p_parameter_declaration(self, p):
        """parameter_declaration : type_specifier declarator
        """
        p[0] = self.aux_declarations(spec=p[1], decls=[dict(decl=p[2], init=None)])[0]

    def p_decl_body(self, p):
        """decl_body : type_specifier init_declarator_list_emp
        """
        if p[2] is not None:
            p[0] = self.aux_declarations(p[1], p[2])
        else:
            p[0] = None

    def p_declaration_list(self, p):
        """declaration_list : declaration
        | declaration_list declaration
        """
        p[0] = p[1] if len(p) == 2 else p[1] + p[2]

    def p_declaration_list_emp(self, p):
        """declaration_list_emp : declaration_list
        | empty
        """
        p[0] = p[1]

    def p_init_declarator_list_emp(self, p):
        """init_declarator_list_emp : init_declarator_list
        | empty
        """
        p[0] = p[1]

    def p_initializer_list(self, p):
        """initializer_list : initializer
        | initializer_list COMMA initializer
        """
        if len(p) == 2:
            p[0] = InitList([p[1]], coord=p[1].coord)
        else:
            if not isinstance(p[1], InitList):
                p[1] = InitList([p[1]], coord=p[1].coord)
            p[1].exprs.append(p[3])
            p[0] = p[1]

    def p_cast_expression(self, p):
        """cast_expression : unary_expression
        | LPAREN type_specifier RPAREN cast_expression
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = Cast(p[2], p[4], coord=self._token_coord(p, 1))

    def p_jump_statement(self, p):
        """jump_statement : BREAK SEMI
        | RETURN empty SEMI
        | RETURN expression SEMI
        """
        if len(p) == 3:
            p[0] = Break(coord=self._token_coord(p, 1))
        else:
            p[0] = Return(p[2], coord=self._token_coord(p, 1))

    def aux_declarations(self, spec, decls):
        aux = []
        for decl in decls:
            assert decl["decl"] is not None
            declaration = Decl(name=None, type=decl["decl"], init=decl.get("init"), coord=decl["decl"].coord,)
            aux.append(self.aux_types(declaration, spec))
        return aux

    def aux_functions(self, spec, decl, param_decls, statements):
        declaration = self.aux_declarations(spec=spec, decls=[dict(decl=decl, init=None)],)[0]
        return FuncDef(spec, declaration, param_decls, statements, decl.coord)

    def aux_types(self, decl, typename):
        type = decl
        while not isinstance(type, VarDecl):
            type = type.type
        decl.name = type.declname
        if not typename:
            type.type = Type("int", coord=decl.coord)
        else:
            type.type = Type(typename.name, coord=typename.coord)
        return decl

    def aux_change_type(self, decl, modifier):
        tail = modifier
        head = modifier
        while tail.type:
            tail = tail.type
        if isinstance(decl, VarDecl):
            tail.type = decl
            return modifier
        else:
            aux = decl
            while not isinstance(aux.type, VarDecl):
                aux = aux.type
            tail.type = aux.type
            aux.type = head
            return decl

    precedence = (
        ('left', 'OR'),
        ('left', 'AND'),
        ('left', 'EQ', 'NE'),
        ('left', 'GT', 'GE', 'LT', 'LE'),
        ('left', 'PLUS', 'MINUS'),
        ('left', 'TIMES', 'DIVIDE', 'MOD'),
    )

if __name__ == "__main__":

    # create argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="Path to file to be parsed", type=str)
    args = parser.parse_args()

    # get input path
    input_file = args.input_file
    input_path = pathlib.Path(input_file)

    # check if file exists
    if not input_path.exists():
        print("ERROR: Input", input_path, "not found", file=sys.stderr)
        sys.exit(1)

    def print_error(msg, x, y):
        print("Lexical error: %s at %d:%d" % (msg, x, y), file=sys.stderr)

    # set error function
    p = UCParser()
    # open file and print ast
    with open(input_path) as f:
        ast = p.parse(f.read())
        ast.show(buf=sys.stdout, showcoord=True)
        
