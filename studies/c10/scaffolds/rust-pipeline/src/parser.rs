use crate::ast::TranslationUnit;
use crate::lexer::Token;

pub fn parse(_tokens: &[Token]) -> Result<TranslationUnit, String> {
    Err("parser not implemented".to_owned())
}
