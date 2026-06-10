// This process should automatically succeed
process TEST_SUCCESS {
    input:
    val dummy_val

    output:
    stdout

    script:
    """
    exit 0
    """
}

// Creates a file on the worker node which is uploaded to the working directory.
process TEST_CREATE_FILE {
    input:
    val dummy_val

    output:
    path ("*.txt"), emit: outfile

    script:
    """
    echo "test" > test.txt
    """
}

// Creates an empty file on the worker node which is uploaded to the working directory.
process TEST_CREATE_EMPTY_FILE {
    input:
    val dummy_val

    output:
    path ("*.txt"), emit: outfile

    script:
    """
    touch test.txt
    """
}

// Creates a file on the worker node which is uploaded to the working directory.
process TEST_CREATE_FOLDER {
    input:
    val dummy_val

    output:
    path ("test"), type: 'dir', emit: outfolder

    script:
    """
    mkdir -p test
    echo "test1" > test/test1.txt
    echo "test2" > test/test2.txt
    """
}

// Stages a file from the working directory to the worker node.
process TEST_INPUT {
    input:
    val dummy_val
    path input

    output:
    stdout

    script:
    """
    cat ${input}
    """
}

// Runs a script from the bin/ directory
process TEST_BIN_SCRIPT {
    input:
    val dummy_val

    output:
    path "*.txt"

    script:
    """
    bash run.sh
    """
}

// Stages a file from a remote file to the worker node.
process TEST_STAGE_REMOTE {
    input:
    val dummy_val
    path input

    output:
    stdout

    script:
    """
    cat ${input}
    """
}

// Stages a file from the working directory to the worker node, copies it and stages it back to the working directory.
process TEST_PASS_FILE {
    input:
    val dummy_val
    path input

    output:
    path "out.txt", emit: outfile

    script:
    """
    cp "${input}" "out.txt"
    """
}

// Stages a folder from the working directory to the worker node, copies it and stages it back to the working directory.
process TEST_PASS_FOLDER {
    input:
    val dummy_val
    path input

    output:
    path "out", type: 'dir', emit: outfolder

    script:
    """
    cp -rL ${input} out
    """
}

// Creates a file on the worker node and uploads to the publish directory.
process TEST_PUBLISH_FILE {

    publishDir { params.outdir ?: file(workflow.workDir).resolve("outputs").toUriString() }, mode: 'copy'

    input:
    val dummy_val

    output:
    path "*.txt"

    script:
    """
    touch test.txt
    """
}

// Creates a file on the worker node and uploads to the publish directory.
process TEST_PUBLISH_FOLDER {

    publishDir { params.outdir ?: file(workflow.workDir).resolve("outputs").toUriString() }, mode: 'copy'

    input:
    val dummy_val

    output:
    path "test", type: 'dir'

    script:
    """
    mkdir -p test
    touch test/test1.txt
    touch test/test2.txt
    """
}


// This process should automatically fail but be ignored.
process TEST_IGNORED_FAIL {
    errorStrategy 'ignore'

    input:
    val dummy_val

    output:
    stdout

    script:
    """
    exit 1
    """
}

// This process moves a file within a working directory.
process TEST_MV_FILE {
    input:
    val dummy_val

    output:
    path "output.txt"

    script:
    """
    touch test.txt
    mv test.txt output.txt
    """
}

// Moves the contents of a folder from within a folder
process TEST_MV_FOLDER_CONTENTS {
    input:
    val dummy_val

    output:
    path "out", type: 'dir', emit: outfolder

    script:
    """
    mkdir -p test
    touch test/test.txt
    mkdir -p out/
    mv test/* out/
    """
}

// This process should create and capture STDOUT
process TEST_STDOUT {
    input:
    val dummy_val

    output:
    stdout

    script:
    """
    """
}

// This process should read in val and echo to STDOUT
process TEST_VAL_INPUT {
    input:
    val dummy_val
    val input

    output:
    stdout

    script:
    """
    echo ${input}
    """
}

process TEST_GPU {

    container { gpu_container }
    accelerator 1
    memory '512 MB'

    input:
    val dummy_val
    val input
    val gpu_container

    output:
    stdout

    script:
    '''
    set -euo pipefail

    PYTHON_BIN="$(command -v python3 || command -v python || true)"
    if [ -z "${PYTHON_BIN}" ]; then
        echo "No python3/python executable found in the selected GPU container" >&2
        exit 1
    fi

    "${PYTHON_BIN}" <<'PY'
    import ctypes
    import ctypes.util
    import os
    import sys

    if sys.version_info[0] < 3:
        raise RuntimeError("TEST_GPU requires Python 3 in the selected GPU container")

    def load_libcuda():
        candidates = []
        found = ctypes.util.find_library("cuda")
        if found:
            candidates.append(found)
        candidates.extend(["libcuda.so.1", "libcuda.so"])
        for directory in os.environ.get("LD_LIBRARY_PATH", "").split(":"):
            if directory:
                candidates.append(os.path.join(directory, "libcuda.so.1"))
        candidates.extend([
            "/usr/lib/x86_64-linux-gnu/libcuda.so.1",
            "/usr/lib64/libcuda.so.1",
            "/usr/local/nvidia/lib64/libcuda.so.1",
            "/usr/local/nvidia/lib/libcuda.so.1",
            "/usr/local/cuda/compat/libcuda.so.1",
        ])

        errors = []
        for candidate in dict.fromkeys(candidates):
            try:
                return ctypes.CDLL(candidate), candidate
            except OSError as exc:
                errors.append(f"{candidate}: {exc}")

        raise RuntimeError(
            "Could not load libcuda.so.1. NVIDIA compute driver capability "
            "is not visible inside the selected GPU container. Tried: "
            + "; ".join(errors)
        )

    cuda, libcuda_path = load_libcuda()

    CUresult = ctypes.c_int
    CUdevice = ctypes.c_int
    CUcontext = ctypes.c_void_p
    CUdeviceptr = ctypes.c_uint64

    def sym(*names):
        for name in names:
            try:
                return getattr(cuda, name)
            except AttributeError:
                pass
        raise AttributeError("Missing CUDA Driver API symbol: " + "/".join(names))

    def bind(names, restype, *argtypes):
        fn = sym(*names)
        fn.restype = restype
        fn.argtypes = argtypes
        return fn

    cuInit = bind(("cuInit",), CUresult, ctypes.c_uint)
    cuGetErrorString = bind(("cuGetErrorString",), CUresult, CUresult, ctypes.POINTER(ctypes.c_char_p))
    cuDriverGetVersion = bind(("cuDriverGetVersion",), CUresult, ctypes.POINTER(ctypes.c_int))
    cuDeviceGetCount = bind(("cuDeviceGetCount",), CUresult, ctypes.POINTER(ctypes.c_int))
    cuDeviceGet = bind(("cuDeviceGet",), CUresult, ctypes.POINTER(CUdevice), ctypes.c_int)
    cuDeviceGetName = bind(("cuDeviceGetName",), CUresult, ctypes.c_char_p, ctypes.c_int, CUdevice)
    cuCtxCreate = bind(("cuCtxCreate_v2", "cuCtxCreate"), CUresult, ctypes.POINTER(CUcontext), ctypes.c_uint, CUdevice)
    cuCtxDestroy = bind(("cuCtxDestroy_v2", "cuCtxDestroy"), CUresult, CUcontext)
    cuCtxSynchronize = bind(("cuCtxSynchronize",), CUresult)
    cuMemAlloc = bind(("cuMemAlloc_v2", "cuMemAlloc"), CUresult, ctypes.POINTER(CUdeviceptr), ctypes.c_size_t)
    cuMemFree = bind(("cuMemFree_v2", "cuMemFree"), CUresult, CUdeviceptr)
    cuMemsetD8 = bind(("cuMemsetD8_v2", "cuMemsetD8"), CUresult, CUdeviceptr, ctypes.c_ubyte, ctypes.c_size_t)
    cuMemcpyDtoH = bind(("cuMemcpyDtoH_v2", "cuMemcpyDtoH"), CUresult, ctypes.c_void_p, CUdeviceptr, ctypes.c_size_t)

    def cuda_error(code):
        message = ctypes.c_char_p()
        if cuGetErrorString(code, ctypes.byref(message)) == 0 and message.value:
            return message.value.decode("utf-8", "replace")
        return f"CUDA error code {code}"

    def check(code, action):
        if code != 0:
            raise RuntimeError(f"{action} failed: {cuda_error(code)}")

    ctx = CUcontext()
    dptr = CUdeviceptr()

    try:
        check(cuInit(0), "cuInit")

        driver_version = ctypes.c_int()
        check(cuDriverGetVersion(ctypes.byref(driver_version)), "cuDriverGetVersion")

        device_count = ctypes.c_int()
        check(cuDeviceGetCount(ctypes.byref(device_count)), "cuDeviceGetCount")
        if device_count.value < 1:
            raise RuntimeError("No CUDA-capable GPU is visible inside the selected GPU container")

        device = CUdevice()
        check(cuDeviceGet(ctypes.byref(device), 0), "cuDeviceGet")

        name = ctypes.create_string_buffer(128)
        check(cuDeviceGetName(name, len(name), device), "cuDeviceGetName")

        check(cuCtxCreate(ctypes.byref(ctx), 0, device), "cuCtxCreate")

        nbytes = 1024 * 1024
        check(cuMemAlloc(ctypes.byref(dptr), nbytes), "cuMemAlloc")
        check(cuMemsetD8(dptr, 0xA5, nbytes), "cuMemsetD8")
        check(cuCtxSynchronize(), "cuCtxSynchronize")

        sample = (ctypes.c_ubyte * 32)()
        check(cuMemcpyDtoH(sample, dptr, len(sample)), "cuMemcpyDtoH")
        if any(byte != 0xA5 for byte in sample):
            raise RuntimeError("GPU memory round-trip verification failed")

        print("CUDA driver probe passed")
        print(f"GPU count: {device_count.value}")
        print(f"First GPU: {name.value.decode('utf-8', 'replace')}")
        print(f"CUDA driver API version: {driver_version.value}")
        print(f"libcuda: {libcuda_path}")

    finally:
        if dptr.value:
            cuMemFree(dptr)
        if ctx.value:
            cuCtxDestroy(ctx)
    PY
    '''
}

// Runs fusion-doctor to validate the Fusion filesystem configuration.
// Prints a text diagnostic report to stdout and saves a JSON report
// to file. Fails if the fusion binary is not available in the task
// environment.
process TEST_FUSION_DOCTOR {

    container 'cr.seqera.io/public/fusion/doctor:1.0.0'
    publishDir { params.outdir ?: file(workflow.workDir).resolve("outputs/fusion").toUriString() }, mode: 'copy'

    input:
    val dummy_val
    path reference_profile
    val rw_buckets
    val ro_buckets
    val cache_path

    output:
    path ("fusion-doctor-report.json"), emit: report

    script:
    def disk_flag = "--check-disk-usage ${cache_path ?: '/tmp'}"
    def redact_flag = params.fusion_redact ? "--redact" : ""
    def ref_profile_flag = !reference_profile.empty() ? "--reference-profile ${reference_profile}" : ""

    // Build bucket args from lists
    def rw_bucket_args = rw_buckets ? rw_buckets.collect { bucket -> "--check-bucket-read-write ${bucket}" }.join(' ') : ""
    def ro_bucket_args = ro_buckets ? ro_buckets.collect { bucket -> "--check-bucket-read-only ${bucket}" }.join(' ') : ""

    """
    #!/bin/bash
    set -euo pipefail

    # Run fusion-doctor and capture exit code
    # Allow validation failures (exit codes 1 and 3) but abort on other errors
    set +e
    fusion-doctor \\
        --output fusion-doctor-report.json \\
        ${ref_profile_flag} \\
        ${disk_flag} \\
        ${redact_flag} \\
        ${rw_bucket_args} \\
        ${ro_bucket_args}
    EXIT_CODE=\$?
    set -e

    # Only allow exit codes 0, 1, and 3 (success and validation failures)
    # Abort on any other exit code (non-validation errors)
    if [[ \$EXIT_CODE -ne 0 && \$EXIT_CODE -ne 1 && \$EXIT_CODE -ne 3 ]]; then
        echo "ERROR: fusion-doctor failed with exit code \$EXIT_CODE (non-validation error)" >&2
        exit \$EXIT_CODE
    fi

    # Exit successfully for validation failures to allow report generation
    exit 0
    """
}

// Aggregates doctor, bench, and objbench JSON reports into a single
// consolidated HTML report and combined JSON report using the Python
// generate_fusion_report.py script.
process FUSION_DOCTOR_GENERATE_REPORT {

    container 'community.wave.seqera.io/library/jinja2_python_uv:7113b0a0e59d95a6'
    publishDir { (params.outdir ? file(params.outdir) : file(workflow.workDir).resolve("outputs")).resolve("fusion").toUriString() }, mode: 'copy'

    input:
    path doctor_report
    path template_file

    output:
    path ("fusion-report.html"), emit: html_report
    path ("fusion-report.json"), emit: json_report

    script:
    """
    generate_fusion_report.py \\
        --doctor ${doctor_report} \\
        --template ${template_file} \\
        --output-html fusion-report.html \\
        --output-json fusion-report.json
    """
}

workflow NF_CANARY {
    take:
    run_tools
    skip_tools
    gpu
    fusion
    gpu_container

    main:
    def default_run_tools = [
        "TEST_SUCCESS",
        "TEST_CREATE_FILE",
        "TEST_MV_FILE",
        "TEST_CREATE_EMPTY_FILE",
        "TEST_CREATE_FOLDER",
        "TEST_INPUT",
        "TEST_BIN_SCRIPT",
        "TEST_STAGE_REMOTE",
        "TEST_PASS_FILE",
        "TEST_PASS_FOLDER",
        "TEST_PUBLISH_FILE",
        "TEST_PUBLISH_FOLDER",
        "TEST_IGNORED_FAIL",
        "TEST_GPU",
        "TEST_MV_FOLDER_CONTENTS",
        "TEST_VAL_INPUT",
        "TEST_FUSION_DOCTOR"
    ]

    def run = run_tools ? run_tools.tokenize(",")*.toUpperCase() : default_run_tools
    def skip = skip_tools.tokenize(",")*.toUpperCase()

    channel.fromList(run.findAll { toolname -> toolname !in skip })
        .flatten()
        .branch { toolname ->
            TEST_BIN_SCRIPT: toolname == "TEST_BIN_SCRIPT"
            TEST_CREATE_EMPTY_FILE: toolname == "TEST_CREATE_EMPTY_FILE"
            TEST_CREATE_FILE: toolname == "TEST_CREATE_FILE"
            TEST_CREATE_FOLDER: toolname == "TEST_CREATE_FOLDER"
            TEST_FUSION_DOCTOR: toolname == "TEST_FUSION_DOCTOR" && fusion
            TEST_GPU: toolname == "TEST_GPU" && gpu
            TEST_IGNORED_FAIL: toolname == "TEST_IGNORED_FAIL"
            TEST_INPUT: toolname == "TEST_INPUT"
            TEST_MV_FILE: toolname == "TEST_MV_FILE"
            TEST_MV_FOLDER_CONTENTS: toolname == "TEST_MV_FOLDER_CONTENTS"
            TEST_PASS_FILE: toolname == "TEST_PASS_FILE"
            TEST_PASS_FOLDER: toolname == "TEST_PASS_FOLDER"
            TEST_PUBLISH_FILE: toolname == "TEST_PUBLISH_FILE"
            TEST_PUBLISH_FOLDER: toolname == "TEST_PUBLISH_FOLDER"
            TEST_STAGE_REMOTE: toolname == "TEST_STAGE_REMOTE"
            TEST_SUCCESS: toolname == "TEST_SUCCESS"
            TEST_VAL_INPUT: toolname == "TEST_VAL_INPUT"
        }
        .set { run_ch }

    channel.of("alpha", "beta", "gamma")
        .collectFile(name: 'sample.txt', newLine: true)
        .set { test_file }

    remote_file = params.remoteFile ? channel.fromPath(params.remoteFile, glob: false) : channel.empty()

    // Parse bucket parameters into lists
    def rw_buckets_list = (params.fusion_read_write_buckets ? params.fusion_read_write_buckets.tokenize(',').collect { bucket -> bucket.trim() } : []) + [workflow.workDir.toUriString()]
    def ro_buckets_list = params.fusion_read_only_buckets ? params.fusion_read_only_buckets.tokenize(',').collect { bucket -> bucket.trim() } : []

    // Build fusion-doctor reference profile YAML from fusion parameters
    def yaml_lines = []
    if (params.fusion_kernel_version_min) {
        yaml_lines.add("kernel_version_min: \"${params.fusion_kernel_version_min}\"")
    }
    if (params.fusion_memory_capacity_gb_min) {
        yaml_lines.add("memory_capacity_gb_min: ${params.fusion_memory_capacity_gb_min}")
    }
    if (params.fusion_disk_capacity_gb_min) {
        yaml_lines.add("disk_capacity_gb_min: ${params.fusion_disk_capacity_gb_min}")
    }
    if (params.fusion_nvme_required != null) {
        yaml_lines.add("nvme_required: ${params.fusion_nvme_required}")
    }
    if (params.fusion_vcpus_min) {
        yaml_lines.add("vcpus_min: ${params.fusion_vcpus_min}")
    }
    if (params.fusion_open_files_min) {
        yaml_lines.add("open_files_min: ${params.fusion_open_files_min}")
    }
    reference_profile_ch = channel.of(yaml_lines.join('\n'))
        .collectFile(name: 'fusion-reference-profile.yaml')

    // Run tests
    TEST_SUCCESS(run_ch.TEST_SUCCESS)
    TEST_CREATE_FILE(run_ch.TEST_CREATE_FILE)
    TEST_CREATE_EMPTY_FILE(run_ch.TEST_CREATE_EMPTY_FILE)
    TEST_CREATE_FOLDER(run_ch.TEST_CREATE_FOLDER)
    TEST_INPUT(run_ch.TEST_INPUT, test_file)
    TEST_BIN_SCRIPT(run_ch.TEST_BIN_SCRIPT)
    TEST_STAGE_REMOTE(run_ch.TEST_STAGE_REMOTE, remote_file)
    TEST_PASS_FILE(run_ch.TEST_PASS_FILE, TEST_CREATE_FILE.out.outfile)
    TEST_PASS_FOLDER(run_ch.TEST_PASS_FOLDER, TEST_CREATE_FOLDER.out.outfolder)
    TEST_PUBLISH_FILE(run_ch.TEST_PUBLISH_FILE)
    TEST_PUBLISH_FOLDER(run_ch.TEST_PUBLISH_FOLDER)
    TEST_IGNORED_FAIL(run_ch.TEST_IGNORED_FAIL)
    TEST_MV_FILE(run_ch.TEST_MV_FILE)
    TEST_MV_FOLDER_CONTENTS(run_ch.TEST_MV_FOLDER_CONTENTS)
    TEST_VAL_INPUT(run_ch.TEST_VAL_INPUT, "Hello World")
    TEST_GPU(run_ch.TEST_GPU, "dummy", gpu_container)

    TEST_FUSION_DOCTOR(run_ch.TEST_FUSION_DOCTOR, reference_profile_ch, rw_buckets_list, ro_buckets_list, params.fusion_cache_path)

    // Generate consolidated fusion report from doctor output
    // Only run FUSION_DOCTOR_GENERATE_REPORT if TEST_FUSION_DOCTOR produced output
    FUSION_DOCTOR_GENERATE_REPORT(
        TEST_FUSION_DOCTOR.out.report,
        file("${projectDir}/assets/templates/fusion_report_template.html"),
    )

    // POC of emitting the channel
    channel.empty()
        .mix(
            TEST_SUCCESS.out,
            TEST_CREATE_FILE.out,
            TEST_CREATE_EMPTY_FILE.out,
            TEST_CREATE_FOLDER.out,
            TEST_INPUT.out,
            TEST_BIN_SCRIPT.out,
            TEST_STAGE_REMOTE.out,
            TEST_PASS_FILE.out,
            TEST_PASS_FOLDER.out,
            TEST_PUBLISH_FILE.out,
            TEST_PUBLISH_FOLDER.out,
            TEST_IGNORED_FAIL.out,
            TEST_MV_FILE.out,
            TEST_MV_FOLDER_CONTENTS.out,
            TEST_VAL_INPUT.out,
            TEST_GPU.out,
            TEST_FUSION_DOCTOR.out,
            FUSION_DOCTOR_GENERATE_REPORT.out.html_report.ifEmpty([]),
            FUSION_DOCTOR_GENERATE_REPORT.out.json_report.ifEmpty([]),
        )
        .set { ch_out }

    emit:
    out = ch_out
}

workflow {
    NF_CANARY(params.run, params.skip, params.gpu, params.fusion, params.gpu_container)
}
