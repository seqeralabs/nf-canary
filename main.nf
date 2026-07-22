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
    /*
    Runs fusion-doctor to validate the Fusion filesystem configuration.
    The reference-profile YAML is staged in as a file (built via collectFile
    in the workflow), avoiding any shell quoting or indentation issues.
    */

<<<<<<< HEAD
    container 'cr.seqera.io/public/fusion/doctor:1.0.0-dev-260420150843'
    tag { meta.run_id }
    publishDir { (params.outdir ? file(params.outdir) : file(workflow.workDir).resolve("outputs/fusion")).toUriString() }, mode: 'copy'
=======
    container 'cr.seqera.io/public/fusion/doctor:1.0.0'
    publishDir { params.outdir ?: file(workflow.workDir).resolve("outputs/fusion").toUriString() }, mode: 'copy'
>>>>>>> origin/main

    input:
        tuple val(dummy_val), val(meta), path(reference_profile), val(rw_buckets), val(ro_buckets)

    output:
        path("fusion-doctor-report-${meta.run_id}.json"), emit: report

    script:
    def disk_flag      = "--check-disk-usage ${meta.cache_path ?: '/tmp'}"
    def redact_flag    = params.fusion_redact ? "--redact" : ""
    def rw_bucket_args = rw_buckets ? rw_buckets.collect { b -> "--check-bucket-read-write ${b}" }.join(' ') : ""
    def ro_bucket_args = ro_buckets ? ro_buckets.collect { b -> "--check-bucket-read-only ${b}"  }.join(' ') : ""

    """
    #!/bin/bash
    set -euo pipefail

    # Run fusion-doctor; allow validation failures (exit 1/3) but abort on others
    set +e
    fusion-doctor \\
        --output fusion-doctor-report-${meta.run_id}.json \\
        --reference-profile ${reference_profile} \\
        ${disk_flag} \\
        ${redact_flag} \\
        ${rw_bucket_args} \\
        ${ro_bucket_args}
    EXIT_CODE=\$?
    set -e

    if [[ \$EXIT_CODE -ne 0 && \$EXIT_CODE -ne 1 && \$EXIT_CODE -ne 3 ]]; then
        echo "ERROR: fusion-doctor failed with exit code \$EXIT_CODE (non-validation error)" >&2
        exit \$EXIT_CODE
    fi
    exit 0
    """
}

process FUSION_DOCTOR_GENERATE_REPORT {
    /*
    Aggregates one or more doctor JSON reports (one per parameter-sweep
    combination) into a single consolidated HTML report and combined JSON
    report using the Python generate_fusion_report.py script.

    When multiple doctor reports exist (parameter sweep), they are all
    staged into the task directory and passed to the script via repeated
    --doctor flags so the report covers every combination.
    */

    container 'community.wave.seqera.io/library/jinja2_python_uv:7113b0a0e59d95a6'
    publishDir { (params.outdir ? file(params.outdir) : file(workflow.workDir).resolve("outputs")).resolve("fusion").toUriString() }, mode: 'copy'

    input:
        path(doctor_reports)   // one or more JSON reports from the sweep
        path(template_file)

    output:
        path("fusion-report.html"), emit: html_report
        path("fusion-report.json"), emit: json_report

    script:
    def doctor_args = doctor_reports.collect { f -> "--doctor ${f}" }.join(' \\\n        ')
    """
    generate_fusion_report.py \\
        ${doctor_args} \\
        --template ${template_file} \\
        --output-html fusion-report.html \\
        --output-json fusion-report.json
    """
}

/* sweepList
*/
/**
 * Split a comma-separated parameter string into a trimmed, non-empty list.
 * Returns an empty list when the value is null, empty, or blank.
 * Used to normalise all sweep parameters before building the Cartesian product.
 *
 * Examples:
 *   sweepList("5.10, 5.15")  → ["5.10", "5.15"]
 *   sweepList("4,8, ,16")    → ["4", "8", "16"]
 *   sweepList(null)           → []
 */
def sweepList(v) {
    v ? v.toString().tokenize(',').collect { p -> p.trim() }.findAll { p -> p } : []
}

workflow FUSION_DOCTOR {
    take:
        trigger_ch              // val channel — one item fires the whole sweep
        kernel_version_min      // e.g. "5.10,5.15"
        memory_gb_min           // e.g. "4,8,16"
        disk_gb_min             // e.g. "100,200,950"
        nvme_required           // e.g. "false,true"
        cpu_cores_min           // e.g. "2,4,16"
        open_files_min          // e.g. "65535,131072,1048576"
        cache_path              // e.g. "/tmp"
        read_write_buckets      // comma-separated bucket URIs
        read_only_buckets       // comma-separated bucket URIs

    main:
        def rw_buckets_list = sweepList(read_write_buckets) + [workflow.workDir.toUriString()]
        def ro_buckets_list = sweepList(read_only_buckets)

        def kernel_sweep = sweepList(kernel_version_min)
        def memory_sweep = sweepList(memory_gb_min)
        def disk_sweep   = sweepList(disk_gb_min)
        def nvme_sweep   = sweepList(nvme_required)
        def cpu_sweep    = sweepList(cpu_cores_min)
        def openf_sweep  = sweepList(open_files_min)
        def cache_sweep  = sweepList(cache_path ?: '/tmp')

        trigger_ch
            .combine(channel.fromList(kernel_sweep))
            .combine(channel.fromList(memory_sweep))
            .combine(channel.fromList(disk_sweep))
            .combine(channel.fromList(nvme_sweep))
            .combine(channel.fromList(cpu_sweep))
            .combine(channel.fromList(openf_sweep))
            .combine(channel.fromList(cache_sweep))
            .map { dummy_val, kernel, memory, disk, nvme, cpu, openf, cache ->
                def parts = []
                if (kernel) parts << "k${kernel.replaceAll('[^a-zA-Z0-9]', '_')}"
                if (memory) parts << "mem${memory}"
                if (disk)   parts << "disk${disk}"
                if (nvme)   parts << "nvme${nvme}"
                if (cpu)    parts << "cpu${cpu}"
                if (openf)  parts << "of${openf}"
                if (cache && cache != '/tmp') parts << "cache${cache.replaceAll('[^a-zA-Z0-9]', '_')}"

                def yaml_lines = []
                if (kernel) yaml_lines << "kernel_version_min: \"${kernel}\""
                if (memory) yaml_lines << "memory_gb_min: ${memory}"
                if (disk)   yaml_lines << "disk_gb_min: ${disk}"
                if (nvme)   yaml_lines << "nvme_required: ${nvme}"
                if (cpu)    yaml_lines << "cpu_cores_min: ${cpu}"
                if (openf)  yaml_lines << "open_files_min: ${openf}"

                def run_id = parts ? parts.join('_') : 'default'
                [run_id, dummy_val, [run_id: run_id, cache_path: cache ?: '/tmp'], yaml_lines.join('\n')]
            }
            .set { sweep_ch }

        // Materialise each per-combination YAML string as a staged file,
        // then rejoin on run_id to rebuild the full process input tuple.
        sweep_ch
            .map { run_id, dummy_val, meta, yaml_text -> [run_id, yaml_text] }
            .collectFile { run_id, yaml_text -> [ "fusion-reference-profile-${run_id}.yaml", yaml_text + '\n' ] }
            .map { f -> [f.baseName.replace('fusion-reference-profile-', ''), f] }
            .join(sweep_ch.map { run_id, dummy_val, meta, yaml_text -> [run_id, dummy_val, meta] })
            .map { run_id, reference_profile, dummy_val, meta ->
                [dummy_val, meta, reference_profile, rw_buckets_list, ro_buckets_list]
            }
            .set { inputs_ch }

    emit:
        inputs = inputs_ch   // tuple: [dummy_val, meta, reference_profile, rw_buckets, ro_buckets]
}

workflow NF_CANARY {
    take:
<<<<<<< HEAD
        run_tools
        skip_tools
        gpu
        fusion
        fusion_kernel_version_min
        fusion_memory_gb_min
        fusion_disk_gb_min
        fusion_nvme_required
        fusion_cpu_cores_min
        fusion_open_files_min
        fusion_cache_path
        fusion_read_write_buckets
        fusion_read_only_buckets
=======
    run_tools
    skip_tools
    gpu
    fusion
    gpu_container
>>>>>>> origin/main

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

    log.info(
        """
          _____
         /_____|D
         |    ◒ >
         /      \\
        """.stripIndent()
    )

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

        channel
            .of("alpha", "beta", "gamma")
            .collectFile(name: 'sample.txt', newLine: true)
            .set { test_file }

        remote_file = params.remoteFile ? channel.fromPath(params.remoteFile, glob:false) : channel.empty()

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

        FUSION_DOCTOR(
            run_ch.TEST_FUSION_DOCTOR,
            fusion_kernel_version_min,
            fusion_memory_gb_min,
            fusion_disk_gb_min,
            fusion_nvme_required,
            fusion_cpu_cores_min,
            fusion_open_files_min,
            fusion_cache_path,
            fusion_read_write_buckets,
            fusion_read_only_buckets
        )

        TEST_FUSION_DOCTOR(FUSION_DOCTOR.out.inputs)

        FUSION_DOCTOR_GENERATE_REPORT(
            TEST_FUSION_DOCTOR.out.report.collect(),
            file("${projectDir}/assets/templates/fusion_report_template.html")
        )

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
                TEST_FUSION_DOCTOR.out.report,
                FUSION_DOCTOR_GENERATE_REPORT.out.html_report.ifEmpty([]),
                FUSION_DOCTOR_GENERATE_REPORT.out.json_report.ifEmpty([])
            )
            .set { ch_out }

    emit:
    out = ch_out
}

workflow {
<<<<<<< HEAD
    NF_CANARY(
        params.run,
        params.skip,
        params.gpu,
        params.fusion,
        params.fusion_kernel_version_min,
        params.fusion_memory_gb_min,
        params.fusion_disk_gb_min,
        params.fusion_nvme_required,
        params.fusion_cpu_cores_min,
        params.fusion_open_files_min,
        params.fusion_cache_path,
        params.fusion_read_write_buckets,
        params.fusion_read_only_buckets
    )
=======
    NF_CANARY(params.run, params.skip, params.gpu, params.fusion, params.gpu_container)

    workflow.onComplete = {
        if (workflow.success) {
            log.info(
                """

               _____
              /_____|D
            \\ |    ◒ > /
            \\/      \\/
                """.stripIndent()
            )
        } else {
            log.info(
                """

                ∩ Ʌ  ╕╒
                |‾|x‾‾‾)̣___
                ‾ ‾‾‾‾
                """.stripIndent()
            )
        }
    }
>>>>>>> origin/main
}
