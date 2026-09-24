mod ast;
mod codegen;
mod ir;
mod lexer;
mod parser;
mod sema;

use std::env;
use std::fs;
use std::path::{Path, PathBuf};

fn usage() -> ! {
    eprintln!("usage: picc INPUT.c -o OUTPUT.s");
    std::process::exit(2);
}

fn parse_args() -> (PathBuf, PathBuf) {
    let args: Vec<_> = env::args_os().skip(1).collect();
    if args.len() != 3 || args[1] != "-o" {
        usage();
    }
    (PathBuf::from(&args[0]), PathBuf::from(&args[2]))
}

fn compile(source: &str) -> Result<String, String> {
    let tokens = lexer::lex(source)?;
    let syntax = parser::parse(&tokens)?;
    let resolved = sema::analyze(syntax)?;
    let program = ir::lower(resolved)?;
    codegen::emit(&program)
}

fn remove_output(path: &Path) {
    let _ = fs::remove_file(path);
}

fn main() {
    let (input, output) = parse_args();
    let source = match fs::read_to_string(&input) {
        Ok(source) => source,
        Err(error) => {
            eprintln!("{}: {error}", input.display());
            std::process::exit(1);
        }
    };

    match compile(&source) {
        Ok(assembly) => {
            if let Err(error) = fs::write(&output, assembly) {
                remove_output(&output);
                eprintln!("{}: {error}", output.display());
                std::process::exit(1);
            }
        }
        Err(error) => {
            remove_output(&output);
            eprintln!("error: {error}");
            std::process::exit(1);
        }
    }
}
