from project_skeleton.cli import main


def test_main_prints_hello(capsys):
    main()
    captured = capsys.readouterr()
    assert captured.out == "Hello, world!\n"
