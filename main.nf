nextflow.enable.dsl = 2

process CPU_SMOKE {
    output:
    path 'cpu.txt'

    script:
    """
    echo cpu-ok > cpu.txt
    """
}

process GPU_SMOKE {
    label 'gpu'

    output:
    path 'gpu.txt'

    script:
    """
    nvidia-smi --query-gpu=name --format=csv,noheader > gpu.txt
    test -s gpu.txt
    cat gpu.txt
    """
}

workflow {
    CPU_SMOKE()
    GPU_SMOKE()
}
