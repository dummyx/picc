use crate::ast::TranslationUnit;

#[derive(Debug, Clone)]
pub struct ResolvedProgram {
    pub syntax: TranslationUnit,
}

pub fn analyze(syntax: TranslationUnit) -> Result<ResolvedProgram, String> {
    Ok(ResolvedProgram { syntax })
}
