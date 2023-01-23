
def validate_fargate_resources(cpu, mem):
    valid_cpu_mem_combinations = {
        256: [512, 1024, 2048],
        512:   list(range(   1024,   4*1024+1, 1024)),
        1024:  list(range( 2*1024,   8*1024+1, 1024)),
        2048:  list(range( 4*1024,  16*1024+1, 1024)),
        4096:  list(range( 8*1024,  30*1024+1, 1024)),
        8192:  list(range(16*1024,  60*1024+1, 4*1024)),
        16384: list(range(32*1024, 120*1024+1, 8*1024)),
    }
    assert (
        cpu in valid_cpu_mem_combinations,
        f"Given CPU '{cpu}' not in allowed list [{', '.join(list(map(str, valid_cpu_mem_combinations.keys())))}]"
    )
    assert (
        valid_cpu_mem_combinations[cpu] == mem,
        f"Given memory '{mem}' not allowed for CPU '{cpu}'"
    )
