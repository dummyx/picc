use crate::sema::ResolvedProgram;

#[derive(Debug, Clone)]
pub struct Program {
    pub resolved: ResolvedProgram,
}

pub fn lower(resolved: ResolvedProgram) -> Result<Program, String> {
    Ok(Program { resolved })
}
