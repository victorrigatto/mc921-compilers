import argparse
import pathlib
import sys
from typing import Dict, List, Tuple
from uc.uc_ast import *
from uc.uc_block import CFG, BasicBlock, Block, ConditionBlock, format_instruction, EmitBlocks
from uc.uc_interpreter import Interpreter
from uc.uc_parser import UCParser
from uc.uc_sema import NodeVisitor, Visitor


class CodeGenerator(NodeVisitor):
    """
    Node visitor class that creates 3-address encoded instruction sequences
    with Basic Blocks & Control Flow Graph.
    """

    def __init__(self, viewcfg: bool):
        self.viewcfg: bool = viewcfg
        self.current_block: Block = None

        # version dictionary for temporaries. We use the name as a Key
        self.fname: str = "_glob_"
        self.versions: Dict[str, int] = {self.fname: 0}

        # The generated code (list of tuples)
        # At the end of visit_program, we call each function definition to emit
        # the instructions inside basic blocks. The global instructions that
        # are stored in self.text are appended at beginning of the code
        self.code: List[Tuple[str]] = []

        self.text: List[Tuple[str]] = []  # Used for global declarations & constants (list, strings)

        # TODO: Complete if needed.      


    def show(self, buf=sys.stdout):
        _str = ""
        for _code in self.code:
            _str += format_instruction(_code) + "\n"
        buf.write(_str)

    def new_temp(self) -> str:
        """
        Create a new temporary variable of a given scope (function name).
        """
        if self.fname not in self.versions:
            self.versions[self.fname] = 1
        name = "%" + "%d" % (self.versions[self.fname])
        self.versions[self.fname] += 1
        return name

    def new_text(self, typename: str) -> str:
        """
        Create a new literal constant on global section (text).
        """
        name = "@." + typename + "." + "%d" % (self.versions["_glob_"])
        self.versions["_glob_"] += 1
        return name

    # You must implement visit_Nodename methods for all of the other
    # AST nodes.  In your code, you will need to make instructions
    # and append them to the current block code list.
    #
    # A few sample methods follow. Do not hesitate to complete or change
    # them if needed.
    
    ################################################################
    # Program / Functions
    ################################################################
    # Program ok
    # FuncDef ok
    # ParamList ok
    ################################################################

    def visit_Program(self, node: Node):
        """
        Visit all of the global declarations.
        """
        # Visit all of the global declarations
        for _decl in node.gdecls:
            self.visit(_decl)
        # At the end of codegen, first init the self.code with
        # the list of global instructions allocated in self.text
        self.code = self.text.copy()
        # Also, copy the global instructions into the Program node
        node.text = self.text.copy()
        # After, visit all the function definitions and emit the
        # code stored inside basic blocks.
        for _decl in node.gdecls:
            if isinstance(_decl, FuncDef):
                # _decl.cfg contains the Control Flow Graph for the function
                # cfg points to start basic block
                bb = EmitBlocks()
                bb.visit(_decl.cfg)
                for _code in bb.code:
                    self.code.append(_code)

        if self.viewcfg:  # evaluate to True if -cfg flag is present in command line
            for _decl in node.gdecls:
                if isinstance(_decl, FuncDef):
                    dot = CFG(_decl.decl.name.name)
                    dot.view(_decl.cfg)  # _decl.cfg contains the CFG for the function
    
    def visit_FuncDef(self, node: Node):
        """
        Initialize the necessary blocks to construct the CFG of the function.
        """
        #print(node)
        # Local auxiliary variables
        aux_param_list = []
        aux_return = self.new_temp()
        
        # Store name and type locally
        self.fname = node.decl.name.name
        self.ftype = node.type.name

        # Create blocks
        block_function = BasicBlock('%' + node.decl.name.name)
        block_end = BasicBlock('%exit')
        
        # function definition

        # Get parameters
        if node.decl.type.args is None:
            #print("empty")
            pass
        else:
            for p in node.decl.type.args.params:
                aux = self.new_temp()
                # aux must be the same otherwise error
                p.gen_location = aux
                aux_param_list.append((p.type.type.name, aux))
                
        block_function.append((('define_' + node.type.name), ('@' + node.decl.name.name), aux_param_list))
        block_function.append(('entry:',))

        #print(node)

        # Function return

        if (node.type.name) == 'void':
            target_return = None
        else:
            target_return = self.new_temp()
            # again must be the same
            block_function.append((('alloc_' + node.type.name), target_return))
            self.return_key = target_return
        
        # Set predecessor and next
        if self.current_block is None:
            #print("erro")
            pass
        else:
            block_function.predecessors.append(self.current_block)
            self.current_block.next_block = block_function
        
        # We are now in the function block
        self.current_block = block_function
        node.cfg = block_function

        self.visit(node.decl)
        node.decl.name.name = "_glob_"

        # Set branch to end
        block_end.predecessors.append(self.current_block)
        self.current_block.branch = block_end
        block_end.append(('exit:',))

        self.visit(node.body)
        if node.type.name == 'void':
            # Return void
            block_end.append(('return_void',))
        else:
            # Return our return
            block_end.append((('load_' + node.type.name), target_return, aux_return))
            block_end.append((('return_' + node.type.name), aux_return))
        
        # End
        self.current_block.next_block = block_end
        self.current_block = None
        
    def visit_ParamList(self, node: Node):
        """
        Visit parameter list.
        """
        # Just visit all parameters
        for p in node.params:
            self.visit(p)
            # Mount type
            p_type = "store_" + p.type.type.name
            # Create name
            p_name = "%" + p.name.name
            # Get location
            _target = p.gen_location
            # Create complete instruction
            instr = (p_type, _target, p_name)
            # Append to our current block
            self.current_block.append(instr)
    
    ################################################################
    # Declarations / Type
    ################################################################
    # Decl ok
    # VarDecl ok
    # ArrayDecl not implemented at P4, will try at P5 and exam
    # FuncDecl ok
    # Type ok
    ################################################################

    def visit_Decl(self, node: Node):
        """
        Visit the types of the declaration (VarDecl, ArrayDecl, FuncDecl).
        """
        # Check VarDecl, FuncDecl for local
        if (self.fname != "_glob_"):
            # VarDecl?
            if (type(node.type) is VarDecl):
                #print(node)
                instr = (("alloc_" + node.type.type.name), ("%" + node.name.name))
                
                # Append instr
                self.current_block.append(instr)
                
                # Set location
                node.name.gen_location = ("%" + node.name.name)

            # FuncDecl?
            elif (type(node.type) is FuncDecl):
                self.visit(node.type)
            
            if node.init is not None:
                # Visit
                self.visit(node.init)

                instr = (("store_" + node.type.type.name), node.init.gen_location, node.name.gen_location,)
                
                # Append instr
                self.current_block.append(instr)

        # Check VarDecl for global
        if (self.fname == "_glob_"):
            # VarDecl?
            if (type(node.type) is VarDecl):
                #print(node)
                if node.init is None:
                    instr = (("global_" + node.type.type.name), ("@" + node.name.name))
                else:
                    instr = (("global_" + node.type.type.name), ("@" + node.name.name), node.init.value)
                    
                # Append instr
                self.text.append(instr)

    def visit_VarDecl(self, node: Node):
        """
        Visit variable declaration.
        """
        # Allocate on stack memory
        _varname = "%" + node.declname.name
        instr = ("alloc_" + node.type.name, _varname)
        self.current_block.append(instr)

        #print(node)
        # Store optional init val
        _init = node.decl.init
        if _init is not None:
            self.visit(_init)
            instr = (
                "store_" + node.type.name,
                _init.gen_location,
                node.declname.gen_location,
            )
            self.current_block.append(instr)
    
    def visit_FuncDecl(self, node: Node):
        """
        Visit function declaration.
        """
        if node.args is None:
            pass #nothing to do if empty
        else:
            self.visit(node.args) #just visit
    
    def visit_Type(self, node: Node):
        """
        Get the matching basic uCType. Done locally.
        """
        # Do nothing: just pass.
        pass
    
    ################################################################
    # Statements
    ################################################################
    # If ok
    # For ok
    # While ok
    # Compound ok
    # Assignment ok
    # Break ok
    # FuncCall ok
    # Assert ok
    # EmptyStatement ok
    # Print ok
    # Read not implemented at P4, will try at P5 and exam
    # Return ok
    ################################################################

    def visit_If(self, node: Node):
        """
        Visit if statement.
        """
        #print(node)
        # Blocks
        block_if = ConditionBlock('%if')
        block_then = BasicBlock('%if_then')
        block_else = BasicBlock(('%if_else'))
        block_end = BasicBlock('%if_end')
        
        # Jump to if block
        self.current_block.branch = block_if
        self.current_block.append(('jump', '%if'))
        
        # Set if block
        self.current_block.next_block = block_if
        self.current_block = block_if
        
        # Now on the if block
        self.current_block.append(('if:',))
        self.visit(node.cond)
        #print(node.cond)
        # Else or end of if?
        if (node.iffalse):
            self.current_block.append(('cbranch', node.cond.gen_location, '%if_then', '%if_else'))
        else:
            self.current_block.append(('cbranch', node.cond.gen_location, '%if_then', '%if_end'))
        # Then
        #print(node.iftrue)
        if (node.iftrue):
            # Set then block
            block_if.taken = block_then
            block_then.predecessors.append(block_if)
            self.current_block.next_block = block_then
            self.current_block = block_then

            # Now on the then block
            self.current_block.append(('if_then:',))
            self.visit(node.iftrue)
            #print(node)
            self.current_block.append(('jump', '%if_end'))
            
            # Set end block for then block
            block_then.branch = block_end
            block_end.predecessors.append(block_then)
        
        # Else
        if (node.iffalse):
            block_if.fall_through = block_else
            block_else.predecessors.append(block_if)
            self.current_block.next_block = block_else
            self.current_block = block_else
            self.current_block.append(('if_else:',))
            self.visit(node.iffalse)
            self.current_block.append(('jump', '%if_end'))
                
            # Set end block for else block
            block_else.branch = block_end
            block_end.predecessors.append(block_else)

        # Set global end
        self.current_block.next_block = block_end
        self.current_block = block_end
        self.current_block.append(('if_end:',))
    
    def visit_For(self, node: Node):
        """
        Visit for statement.
        """
        # Create blocks
        block_test = ConditionBlock('%for_test')
        block_body = BasicBlock('%for_body')
        block_increment = BasicBlock('%for_increment')
        block_final_increment = BasicBlock('%for_final_increment')
        block_end = BasicBlock('%for_end')

        # For start
        self.visit(node.init)

        # If a break occurs
        self.current_break = 'for_end'

        # Lets go test the condition
        self.current_block.append(('jump', '%for_test'))

        # Set branch and predecessor
        self.current_block.branch = block_test
        block_test.predecessors.append(self.current_block)
        block_test.predecessors.append(block_increment)

        # Go to condition block
        self.current_block.next_block = block_test
        self.current_block = block_test

        # We are now on the test block
        self.current_block.append(('for_test:',))

        # Lets test the condition
        self.visit(node.cond)
        self.current_block.append(('cbranch', node.cond.gen_location, '%for_body', '%for_final_increment'))

        # Set blocks for the condition result
        block_test.taken = block_body
        block_test.fall_through = block_final_increment

        # Set test block as predecessor of body block
        block_body.predecessors.append(block_test)

        # Go to body block
        self.current_block.next_block = block_body
        self.current_block = block_body

        # We are now on the body block
        self.current_block.append(('for_body:',))

        # Visit body of the loop
        self.visit(node.body)
        # Increment loop
        self.current_block.append(('jump', '%for_increment'))

        # Connect increment block to body block
        self.current_block.branch = block_increment

        # Go to increment block
        self.current_block.next_block = block_increment
        self.current_block = block_increment

        # We are now on the increment block
        self.current_block.append(('for_increment:',))

        # Visit incrementation part
        self.visit(node.next)

        # Lets go back to test the condition again
        self.current_block.append(('jump', '%for_test'))

        # Set up final increment block, because we need that increment one more time
        self.current_block.next_block = block_final_increment
        self.current_block = block_final_increment

        # We are now on the final increment block
        self.current_block.append(('for_final_increment:',))

        # Visit the increment part for the last time
        self.visit(node.next)

        # Go to end block now
        self.current_block.append(('jump', '%for_end'))

        # Set final increment as end predecessor
        block_end.predecessors.append(block_final_increment)

        # Set to end block
        self.current_block.next_block = block_end
        self.current_block = block_end

        # Now finally on the end block
        self.current_block.append(('for_end:',))
    
    def visit_While(self, node: Node):
        """
        Visit while statement.
        """
        # Blocks
        block_test = ConditionBlock('%while_test')
        block_body = BasicBlock('%while_body')
        block_end = BasicBlock('%while_end')

        # Link current block to condition block
        block_test.predecessors.extend([self.current_block, block_body])
        block_test.taken = block_body
        block_test.fall_through = block_end

        # Branch
        self.current_block.branch = block_test
        self.current_block.append(('jump', '%while_test'))
        self.current_block.next_block = block_test

        self.current_break = 'while_end'

        # Condition
        self.current_block = block_test
        self.current_block.append(('while_test:',))
        self.visit(node.cond)
        self.current_block.append(('cbranch', node.cond.gen_location, '%while_test', '%while_end'))

        # Link
        block_body.predecessors.append(block_test)
        block_body.branch = block_test

        # Loop
        self.current_block.next_block = block_body
        self.current_block = block_body
        self.current_block.append(('while_test:',))
        self.visit(node.body)
        self.current_block.append(('jump', '%while_test'))

        # End
        self.current_block.next_block = block_end
        self.current_block = block_end
        self.current_block.append(('while_test:',))
    
    def visit_Compound(self, node: Node):
        """
        Visit compound statement.
        """
        # Visit the list of block items (declarations or statements).
        if (node.citens is not None and len(node.citens) > 0):
            for item in node.citens:
                self.visit(item)
        else:
            pass
    
    def visit_Assignment(self, node: Node):
        """
        Visit assignment statement.
        """
        # Auxiliary variables
        ops = {'+=':'add', '-=':'sub', '*=':'mul', '/=':'div', '%=':'mod'}
        
        # Visit
        self.visit(node.rvalue)
    
        # Visit ops
        if node.op in ops:
            # Instr for ID or ArrayRef
            if (type(node.lvalue) is ID):
                instr = ((ops[node.op] + '_' + node.lvalue.type.typename), ('%' + node.lvalue.name), node.rvalue.gen_location)
            elif (type(node.lvalue) is ArrayRef):
                self.visit(node.lvalue)
                instr = ((ops[node.op] + '_' + node.lvalue.type.type.type.name + '_*'), ('%' + node.lvalue.gen_location), node.rvalue.gen_location)
            self.current_block.append(instr)
       
        # Instr for ID or ArrayRef
        if (type(node.lvalue) is ID):
            instr = ((('store_' + node.lvalue.type.typename), node.rvalue.gen_location, ('%'+node.lvalue.name)))
        elif (type(node.lvalue) is ArrayRef):
            self.visit(node.lvalue)
            instr = ((('store_' + node.lvalue.type.type.type.name + '_*'), node.rvalue.gen_location, node.lvalue.gen_location))
        
        self.current_block.append(instr)
    
    def visit_Break(self, node: Node):
        """
        Visit break statement.
        """
        # Just jump
        instr = ('jump', ('%' + self.current_break))
        self.current_block.append(instr)

    def visit_FuncCall(self, node: Node):
        """
        Visit function call statement.
        """
        #print(node)
        # Auxiliary variables
        aux = self.new_temp()

        # Auxiliary method
        def aux_Append(type, target):
            # Create instruction
            instr = ('param_' + type, target)

            # Append to current block
            self.current_block.append(instr)

        if node.args is None:
            #print(node)
            pass
        elif type(node.args) is not ExprList:
            self.visit(node.args)

            # Constant?
            if type(node.args) is not Constant:
                # Use typename
                aux_Append(node.args.type.typename, node.args.gen_location)
        else:
            # Visit all expressions
            for e in node.args.exprs:
                self.visit(e)
                #print(e)
                #print(type(e))
                # Check if not Constant
                if type(e) is not Constant:
                    # Use typename
                    aux_Append(e.type.typename, e.gen_location)
                else:
                    # Use type
                    aux_Append(e.type, e.gen_location)

        # Finally create call instr
        instr = (('call_' + node.name.type), ('@' + node.name.name), aux)

        self.current_block.append(instr)
        node.gen_location = aux

    def visit_Assert(self, node: Node):
        # Labels to make our life easier
        label_assert = 'assert'
        label_true = 'assert_true'
        label_false = 'assert_false'

        # Blocks
        condition_block = ConditionBlock('%' + label_assert)
        block_true = BasicBlock('%' + label_true)
        block_false = BasicBlock('%' + label_false)

        # Link current block to condition block
        self.current_block.branch = condition_block
        condition_block.predecessors.append(self.current_block)

        # Jump to condition block
        instr = ('jump', '%' + label_assert)
        self.current_block.append(instr)

        # Setup condition block
        self.current_block.next_block = condition_block
        self.current_block = condition_block

        # We are now on the condition block
        self.current_block.append((label_assert + ':',))
        
        # Visit
        self.visit(node.expr)
        
        # Conditional branch for assertion
        instr = ('cbranch', node.expr.gen_location, ('%' + label_true), ('%' + label_false))
        self.current_block.append(instr)

        # Assert condition fall through
        condition_block.fall_through = block_false
        block_false.predecessors.append(condition_block)
        condition_block.next_block = block_false
        self.current_block = block_false

        # Block false, print assert error and exit
        self.current_block.append((label_false + ':',))
        text = self.new_text('str')
        instr = ('global_string', text, ('assertion_fail on ' + str(node.expr.coord.line) + ':' + str(node.expr.coord.column)))
        self.text.append(instr)
        self.current_block.append(('print_string', text))
        self.current_block.append(('jump', '%exit'))

        # Assert condition taken
        condition_block.taken = block_true
        block_true.predecessors.append(condition_block)
        self.current_block.next_block = block_true
        self.current_block = block_true

        # Block true, continue program flow
        self.current_block.append((label_true + ':',))

    def visit_EmptyStatement(self, node: Node):
        """
        Visit empty statement.
        """
        # Do nothing: just pass.
        pass

    def visit_Print(self, node: Node):
        """
        Visit print statement.
        """
        #print(node)
        # Auxiliary methods
        def aux_Append(type, source):
            instr = ("print_" + type, source)
            self.current_block.append(instr)

        def aux_getType(aux):
            # Find type
            if(type(aux) is ID):
                #print(expression.type)
                return aux.type.typename
            elif(type(aux) is FuncCall):
                return aux.name.type
            elif(type(aux) is ArrayRef):
                #print(expression.name.type.type.type)
                return aux.name.type.type.type.name
            else:
                return aux.type

        if(node.expr is None):
            # Handle cases when it might be None
            self.current_block.append(("print_void",))
        else:
            # Handle list of expressions
            if(type(node.expr) is ExprList):
                for e in node.expr.exprs:
                    # Visit each of them
                    self.visit(e)
                    aux_Append((aux_getType(e)), e.gen_location)
            else:
                self.visit(node.expr) 
                aux_Append((aux_getType(node.expr)), node.expr.gen_location)

    def visit_Read(self, node: Node):
        """
        Visit read statement.
        """
        # Do nothing: just pass.
        pass

    def visit_Return(self, node: Node):
        """
        Visit return statement.
        """
        #print(node)
        if (node.expr is None):
            # Just jump to exit if no expression
            instr = ('jump', '%exit')
            self.current_block.append(instr)
        else:
            # Visit
            self.visit(node.expr)

            # Get type
            f_type = self.ftype

            # Get return
            f_return = self.return_key
            
            # Get location
            f_location = node.expr.gen_location

            # Create return instruction
            instr = ("store_" + f_type, f_location, f_return,)
            self.current_block.append(instr)

    ################################################################
    # Expressions
    ################################################################
    # Constant ok
    # ID ok
    # BinaryOp ok
    # UnaryOp ok
    # ExprList ok
    # ArrayRef not implemented at P4, will try at P5 and exam
    # InitList ok
    ################################################################

    def visit_Constant(self, node: Node):
        """
        Visit constant expression.
        """
        if node.type == "string":
            _target = self.new_text("str")
            instr = ("global_string", _target, node.value)
            self.text.append(instr)
        else:
            # Create a new temporary variable name
            _target = self.new_temp()
            # Make the SSA opcode and append to list of generated instructions
            instr = ("literal_" + node.type, node.value, _target)
            self.current_block.append(instr)
        # Save the name of the temporary variable where the value was placed
        node.gen_location = _target

    def visit_ID(self, node: Node):
        """
        Visit ID.
        """
        # Global
        name = ('@' + node.name)
        
        if not any(name == vars[1] for vars in self.text):
            name = '%' + node.name
        
        # Create instr and append
        aux = self.new_temp()
        node.gen_location = aux
        instr = ("load_" + node.type.typename, name, aux)
        self.current_block.append(instr)
        
    def visit_BinaryOp(self, node: Node):
        """
        Visit binary operation expression.
        """
        #print(node)
        # Strings for operations
        if node.op == '==':
            op_str = 'eq'
        elif node.op == '!=':
            op_str = 'ne'
        elif node.op == '<':
            op_str = 'lt'
        elif node.op == '<=':
            op_str = 'le'
        elif node.op == '>':
            op_str = 'gt'
        elif node.op == '>=':
            op_str = 'ge'
        elif node.op == '+':
            op_str = 'add'
        elif node.op == '-':
            op_str = 'sub'
        elif node.op == '*':
            op_str = 'mul'
        elif node.op == '/':
            op_str = 'div'
        elif node.op == '%':
            op_str = 'mod'
        elif node.op == '&&':
            op_str = 'and'
        elif node.op == '||':
            op_str = 'or'
        elif node.op == '!':
            op_str = 'not'

        # Visit left and right
        self.visit(node.rvalue)
        self.visit(node.lvalue)

        #print(node.lvalue)

        # Mount and append instr based on value type
        if(type(node.lvalue) is FuncCall):
            aux = self.new_temp()
            op = (op_str + "_" + node.lvalue.name.type)
            instr = (op, node.lvalue.gen_location, node.rvalue.gen_location, aux)
            self.current_block.append(instr)
            node.gen_location = aux # Store location
        elif(type(node.lvalue) is ArrayRef):
            aux = self.new_temp()
            op = (op_str + "_" + node.lvalue.type.type.type.name)
            instr = (op, node.lvalue.gen_location, node.rvalue.gen_location, aux)
            self.current_block.append(instr)
            node.gen_location = aux # Store location
        else:
            aux = self.new_temp()
            op = (op_str + "_" + node.lvalue.type.typename)
            instr = (op, node.lvalue.gen_location, node.rvalue.gen_location, aux)
            self.current_block.append(instr)
            node.gen_location = aux # Store location
        
    def visit_UnaryOp(self, node: Node):
        """
        Visit unary operation expression.
        """
        # Aux method to append instr
        def aux_Append(op, *operands):
            self.current_block.append((op, *operands))

        # Aux method to mount instr
        def aux_MountInstr(op, postfix = False):
            aux = self.new_temp()
            instr = ((op + ('_' + node.expr.type.typename)))
            self.current_block(instr, node.expr.gen_location, aux_temp, aux)
            if postfix:
                node.gen_location = aux
            self.current_block('store_int', aux, ('%' + node.expr.name))

        # Visit
        self.visit(node.expr)
        #print(node.expr)

        # Cases ++ p++ -- p--
        if node.op in ('++', 'p++', '--', 'p--'):
                aux_temp = self.new_temp()
                aux_Append("literal_int", 1, aux_temp)
                prefix = 'add' if node.op.endswith('++') else 'sub'
                # Sufixo
                postfix = node.op.startswith('p')
                aux_MountInstr(prefix, postfix)
                # Else
                if not postfix:
                    node.gen_location = node.expr.gen_location
        # Cases ! -
        elif node.op == '!':
            aux_temp = self.new_temp()
            aux_Append('not_bool', node.expr.gen_location, aux_temp)
            node.gen_location = aux_temp
        elif node.op == '-':
            aux_temp = self.new_temp()
            aux_Append("literal_int", 0, aux_temp)
            aux2_temp = self.new_temp()
            aux_Append('sub_' + node.expr.type, aux_temp, node.expr.gen_location, aux2_temp)
            node.gen_location = aux2_temp
        else:
            pass

    def visit_ExprList(self, node: Node):
        """
        Visit expression list.
        """
        # Do nothing: just pass.
        pass

    def visit_ArrayRef(self, node: Node):
        """
        Visit expression list.
        """
        # Do nothing: just pass.
        pass

    def visit_InitList(self, node: Node):
        """
        Visit initialization list.
        """
        # Do nothing: just pass.
        pass

    ################################################################
    # Auxiliary Methods
    ################################################################

    def mountOpInstr(op, postfix = False):
        aux = self.new_temp()
        instr = ((op + ('_' + node.expr.type.typename)))
        self.current_block(instr, node.expr.gen_location, aux_temp, aux)
        if postfix:
            node.gen_location = aux
        self.current_block('store_int', aux, ('%' + node.expr.name))

    def appendCurrBlock(opcode, type, target):
        """
        Auxiliary method to append instructions to current block.
        """
        instr = (opcode + type, target)
        return self.current_block.append(instr)

    def getFuncParams(self, node: Node):
        """
        Auxiliary method to get function parameters.
        """
        aux = [(param.type.type.name, self.new_temp()) for param in node.decl.type.args.params]
        for param, (type, name) in zip(node.decl.type.args.params, aux):
            param.gen_location = name
        return aux

if __name__ == "__main__":

    # create argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input_file",
        help="Path to file to be used to generate uCIR. By default, this script only runs the interpreter on the uCIR. \
              Use the other options for printing the uCIR, generating the CFG or for the debug mode.",
        type=str,
    )
    parser.add_argument(
        "--ir",
        help="Print uCIR generated from input_file.",
        action="store_true",
    )
    parser.add_argument(
        "--cfg", help="Show the cfg of the input_file.", action="store_true"
    )
    parser.add_argument(
        "--debug", help="Run interpreter in debug mode.", action="store_true"
    )
    args = parser.parse_args()

    print_ir = args.ir
    create_cfg = args.cfg
    interpreter_debug = args.debug

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

    gen = CodeGenerator(create_cfg)
    gen.visit(ast)
    gencode = gen.code

    if print_ir:
        print("Generated uCIR: --------")
        gen.show()
        print("------------------------\n")

    vm = Interpreter(interpreter_debug)
    vm.run(gencode)
    
