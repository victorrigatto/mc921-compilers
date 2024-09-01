from pathlib import Path
import timeout_decorator
import pytest
from uc.uc_code import CodeGenerator
from uc.uc_interpreter import Interpreter
from uc.uc_parser import UCParser
from uc.uc_sema import Visitor
from uc.uc_analysis import DataFlow
from contextlib import redirect_stdout, redirect_stderr
import io

name =  [
        "t01",
        "t02",
        "t03",
        "t04",
        "t05",
        "t06",
        "t07",
        "t08",
        "t09",
        "t10",
        "t11",
        "t12",
        "t13",
        "t14",
        "t15",
        "t16",
        "t17",
        "t18",
        "t19",
        "t20",
    ]

def resolve_test_files(test_name):
    input_file = test_name + ".in"
    expected_file = test_name + ".out"
    speedup_file = test_name + ".speedup"

    # get current dir
    current_dir = Path(__file__).parent.absolute()

    # get absolute path to inputs folder
    test_folder = current_dir / Path("in-out")

    # get input path and check if exists
    input_path = test_folder / Path(input_file)
    assert input_path.exists()

    # get expected test file real path
    expected_path = test_folder / Path(expected_file)
    assert expected_path.exists()

    # get expected speedup file real path
    speedup_path = test_folder / Path(speedup_file)
    assert speedup_path.exists()

    return input_path, expected_path,  speedup_path


@pytest.mark.timeout(30)
@pytest.mark.parametrize(
    "test_name", name
)
# capfd will capture the stdout/stderr outputs generated during the test
def test_analysis(test_name, capsys):
    input_path, expected_path, _ = resolve_test_files(test_name)

    p = UCParser(debug=False)
    with open(input_path) as f_in, open(expected_path) as f_ex:
        ast = p.parse(f_in.read())
        sema = Visitor()
        sema.visit(ast)
        gen = CodeGenerator(False)
        gen.visit(ast)
        gencode = gen.code
        opt = DataFlow(False)
        opt.visit(ast)
        optcode = opt.code
        vm = Interpreter(False)
        with pytest.raises(SystemExit) as sys_error:
            vm.run(optcode)
        captured = capsys.readouterr()
        assert sys_error.value.code == 0
        expect = f_ex.read()
    assert captured.out == expect
    assert captured.err == ""
    assert len(gencode)/len(optcode) > 1.1

@timeout_decorator.timeout(30)
def run_with_timeout(optcode):
    vm = Interpreter(False)
    try:
        vm.run(optcode)
    except SystemExit as e:
        return e.code
    return None

@pytest.mark.timeout(30)
@pytest.mark.parametrize(
    "test_name", name
)
# capfd will capture the stdout/stderr outputs generated during the test
def test_bonus(test_name, capsys):
    input_path, expected_path, speedup_path = resolve_test_files(test_name)

    p = UCParser(debug=False)
    with open(input_path) as f_in, open(expected_path) as f_ex:
        ast = p.parse(f_in.read())
        sema = Visitor()
        sema.visit(ast)
        gen = CodeGenerator(False)
        gen.visit(ast)
        gencode = gen.code
        opt = DataFlow(False)
        opt.visit(ast)
        optcode = opt.code
        vm = Interpreter(False)
        with pytest.raises(SystemExit) as sys_error:
            vm.run(optcode)
        captured = capsys.readouterr()
        assert sys_error.value.code == 0
        expect = f_ex.read()
    assert captured.out == expect
    assert captured.err == ""

    with open(speedup_path) as f_sp:
        reference = f_sp.read().split()
    ref_speedup = float(reference[6])
    assert len(optcode) != 0
    assert round(len(gencode)/len(optcode), 2) > ref_speedup

def speedup_points():
    total_grade = 0
    for test_name in name:
        input_path, expected_path, speedup_path = resolve_test_files(test_name)
        cap_stdout = io.StringIO()
        cap_stderr = io.StringIO()
        code_err = -1
        
        with redirect_stdout(cap_stdout), redirect_stderr(cap_stderr):
            try:
                p = UCParser(debug=False)
                with open(input_path) as f_in, open(expected_path) as f_ex:
                    ast = p.parse(f_in.read())
                    sema = Visitor()
                    sema.visit(ast)
                    gen = CodeGenerator(False)
                    gen.visit(ast)
                    gencode = gen.code
                    opt = DataFlow(False)
                    opt.visit(ast)
                    optcode = opt.code
                    code_err = run_with_timeout(optcode)
                    expect = f_ex.read()
            except Exception:
                print("Test failed", test_name, 0.0)
                continue
        if(cap_stdout.getvalue() != expect or cap_stderr.getvalue() != "" or len(gencode)/len(optcode) <= 1.1 or code_err != 0):
            print("Test failed", test_name, 0.0)
            continue

        with open(speedup_path) as f_sp:
            reference = f_sp.read().split()
        grade = 0
        ref_speedup = float(reference[6])
        if len(optcode) != 0:
            grade = round(len(gencode)/len(optcode), 2)
            grade = 0.55 if grade > ref_speedup else 0.5
        print("{} {:.2f}".format(test_name, grade))
        total_grade += grade
    print("{} {:.2f}".format("[Total]", total_grade))


if __name__ == "__main__":
    speedup_points()
