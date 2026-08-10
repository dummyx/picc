use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::ExitCode;

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("{message}");
            ExitCode::from(1)
        }
    }
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 4 || args[2] != "-o" {
        return Err("usage: picc INPUT.c -o OUTPUT.s".into());
    }
    let input = fs::read_to_string(&args[1]).map_err(|error| error.to_string())?;
    if !input.contains("int main(void)") || !input.contains('{') || !input.contains('}') {
        return Err("unsupported or malformed program".into());
    }
    let after_return = input
        .split_once("return")
        .ok_or_else(|| "missing return".to_string())?
        .1;
    let (value_text, _) = after_return
        .split_once(';')
        .ok_or_else(|| "missing semicolon".to_string())?;
    let value: i32 = value_text
        .trim()
        .parse()
        .map_err(|_| "mock compiler only accepts a decimal constant".to_string())?;
    let output = PathBuf::from(&args[3]);
    fs::write(
        output,
        format!(".globl main\nmain:\n  mov ${value}, %eax\n  ret\n"),
    )
    .map_err(|error| error.to_string())?;
    Ok(())
}
