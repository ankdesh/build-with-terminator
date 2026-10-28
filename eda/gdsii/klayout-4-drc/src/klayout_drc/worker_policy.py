"""Worker-only syscall policy: allow threads, deny new processes and namespaces.

This keeps the address-space limit meaningful for the complete candidate worker.
Bubblewrap provides file and network isolation; this filter is an additional gate.
"""
import ctypes
import errno


def install():
    library = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    class Comparison(ctypes.Structure):
        _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_int),
                    ('datum_a', ctypes.c_uint64), ('datum_b', ctypes.c_uint64)]
    library.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
        ctypes.c_int, ctypes.c_uint, ctypes.POINTER(Comparison)]
    context = library.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError('Cannot initialize worker syscall policy')
    try:
        rules = [('fork', errno.EPERM, None), ('vfork', errno.EPERM, None),
                 ('clone3', errno.ENOSYS, None), ('unshare', errno.EPERM, None),
                 ('setns', errno.EPERM, None),
                 ('clone', errno.EPERM, Comparison(0, 7, 0x10000, 0))]  # CLONE_THREAD
        for name, error, comparison in rules:
            number = library.seccomp_syscall_resolve_name(name.encode())
            if number < 0:
                continue
            pointer = ctypes.byref(comparison) if comparison is not None else None
            if library.seccomp_rule_add_array(context, 0x50000 | error, number,
                                              int(comparison is not None), pointer):
                raise RuntimeError(f'Cannot install worker rule for {name}')
        if library.seccomp_load(context):
            raise RuntimeError('Cannot load worker syscall policy')
    finally:
        library.seccomp_release(context)
