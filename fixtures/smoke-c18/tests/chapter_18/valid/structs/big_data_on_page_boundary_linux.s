	.text
	.globl helper_value
helper_value:
	movl $42, %eax
	ret
	.section .note.GNU-stack,"",@progbits
