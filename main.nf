process TEST_SUCCESS {
    /*
    This process should automatically succeed
    */

    input:
        val(dummy_val)

    output:
        stdout

    script:
    """
    exit 0
    """
}

process TEST_CREATE_FILE {
    /*
    Creates a file on the worker node which is uploaded to the working directory.
    */

    input:
        val(dummy_val)

    output:
        path("*.txt"), emit: outfile

    script:
    """
    echo "test" > test.txt
    """
}

process TEST_CREATE_EMPTY_FILE {
    /*
    Creates an empty file on the worker node which is uploaded to the working directory.
    */

    input:
        val(dummy_val)

    output:
        path("*.txt"), emit: outfile

    script:
    """
    touch test.txt
    """
}

process TEST_CREATE_FOLDER {
    /*
    Creates a file on the worker node which is uploaded to the working directory.
    */

    input:
        val(dummy_val)

    output:
        path("test"), type: 'dir', emit: outfolder

    script:
    """
    mkdir -p test
    echo "test1" > test/test1.txt
    echo "test2" > test/test2.txt
    """
}

process TEST_INPUT {
    /*
    Stages a file from the working directory to the worker node.
    */

    input:
        val(dummy_val)
        path input

    output:
        stdout

    script:
    """
    cat $input
    """
}

process TEST_BIN_SCRIPT {
    /*
    Runs a script from the bin/ directory
    */

    input:
        val(dummy_val)

    output:
        path("*.txt")

    script:
    """
    bash run.sh
    """
}

process TEST_STAGE_REMOTE {
    /*
    Stages a file from a remote file to the worker node.
    */

    input:
        val(dummy_val)
        path input

    output:
        stdout

    script:
    """
    cat $input
    """
}

process TEST_PASS_FILE {
    /*
    Stages a file from the working directory to the worker node, copies it and stages it back to the working directory.
    */

    input:
        val(dummy_val)
        path input

    output:
        path "out.txt", emit: outfile

    script:
    """
    cp "$input" "out.txt"
    """
}

process TEST_PASS_FOLDER {
    /*
    Stages a folder from the working directory to the worker node, copies it and stages it back to the working directory.
    */

    input:
        val(dummy_val)
        path input

    output:
        path "out", type: 'dir', emit: outfolder

    script:
    """
    cp -rL $input out
    """
}

process TEST_PUBLISH_FILE {
    /*
    Creates a file on the worker node and uploads to the publish directory.
    */

    publishDir { params.outdir ?: file(workflow.workDir).resolve("outputs").toUriString()  }, mode: 'copy'

    input:
        val(dummy_val)

    output:
        path("*.txt")

    script:
    """
    touch test.txt
    """
}

process TEST_PUBLISH_FOLDER {
    /*
    Creates a file on the worker node and uploads to the publish directory.
    */

    publishDir { params.outdir ?: file(workflow.workDir).resolve("outputs").toUriString()  }, mode: 'copy'

    input:
        val(dummy_val)

    output:
        path("test", type: 'dir')

    script:
    """
    mkdir -p test
    touch test/test1.txt
    touch test/test2.txt
    """
}


process TEST_IGNORED_FAIL {
    /*
    This process should automatically fail but be ignored.
    */
    errorStrategy 'ignore'

    input:
        val(dummy_val)

    output:
        stdout

    script:
    """
    exit 1
    """
}

process TEST_MV_FILE {
    /*
    This process moves a file within a working directory.
    */

    input:
        val(dummy_val)

    output:
        path "output.txt"

    script:
    """
    touch test.txt
    mv test.txt output.txt
    """

}

process TEST_MV_FOLDER_CONTENTS {
    /*
    Moves the contents of a folder from within a folder
    */

    input:
        val(dummy_val)

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

process TEST_STDOUT {
    /*
    This process should create and capture STDOUT
    */

    input:
        val(dummy_val)

    output:
        stdout

    script:
    """
    """
}

process TEST_VAL_INPUT {
    /*
    This process should read in val and echo to STDOUT
    */


    input:
        val(dummy_val)
        val input

    output:
        stdout

    script:
    """
    echo $input
    """
}

process TEST_GPU {

    container 'pytorch/pytorch:latest'
    conda 'pytorch::pytorch=2.5.1 pytorch::torchvision=0.20.1 nvidia::cuda=12.1'
    accelerator 1
    memory '10G'

    input:
        val(dummy_val)
        val input

    output:
        stdout


    script:
    """
    #!/usr/bin/env python
    import torch
    import time

    # Function to print GPU and CUDA details
    def print_gpu_info():
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            cuda_version = torch.version.cuda
            print(f"GPU: {gpu_name}")
            print(f"CUDA Version: {cuda_version}")
        else:
            print("CUDA is not available on this system.")

    # Define a simple function to perform some calculations on the CPU
    def cpu_computation(size):
        x = torch.rand(size, size)
        y = torch.rand(size, size)
        result = torch.mm(x, y)
        return result

    # Define a simple function to perform some calculations on the GPU
    def gpu_computation(size):
        x = torch.rand(size, size, device='cuda')
        y = torch.rand(size, size, device='cuda')
        result = torch.mm(x, y)
        torch.cuda.synchronize()  # Ensure the computation is done
        return result

    # Print GPU and CUDA details
    print_gpu_info()

    # Define the size of the matrices
    size = 10000

    # Measure time for CPU computation
    start_time = time.time()
    cpu_result = cpu_computation(size)
    cpu_time = time.time() - start_time
    print(f"CPU computation time: {cpu_time:.4f} seconds")

    # Measure time for GPU computation
    start_time = time.time()
    gpu_result = gpu_computation(size)
    gpu_time = time.time() - start_time
    print(f"GPU computation time: {gpu_time:.4f} seconds")

    # Optionally, verify that the results are close (they should be if the calculations are the same)
    if torch.allclose(cpu_result, gpu_result.cpu()):
        print("Results are close enough!")
    else:
        print("Results differ!")

    # Print the time difference
    time_difference = cpu_time - gpu_time
    print(f"Time difference (CPU - GPU): {time_difference:.4f} seconds")

    if time_difference < 0:
        raise Exception("GPU is slower than CPU indicating no GPU utilization")
    """

}

process TEST_FUSION_DOCTOR {
    /*
    Runs fusion doctor to validate the Fusion filesystem configuration.
    The reference-profile YAML is staged in as a file (built via collectFile
    in the workflow), avoiding any shell quoting or indentation issues.
    */

    tag { meta.run_id }
    publishDir { (params.outdir ? file(params.outdir) : file(workflow.workDir).resolve("outputs/fusion")).toUriString() }, mode: 'copy'

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

    # TODO(amiranda): Workaround to circumvent the lack of dedicated container
    # Check if fusion is executable, not just if it exists in PATH
    if ! fusion --version >/dev/null 2>&1; then
      if command -v fusion.mock >/dev/null 2>&1; then
        fusion() { fusion.mock "\$@"; }
        export -f fusion
      fi
    fi

    # Run fusion doctor; allow validation failures (exit 1/3) but abort on others
    set +e
    fusion doctor \\
        --output fusion-doctor-report-${meta.run_id}.json \\
        --reference-profile ${reference_profile} \\
        ${disk_flag} \\
        ${redact_flag} \\
        ${rw_bucket_args} \\
        ${ro_bucket_args}
    EXIT_CODE=\$?
    set -e

    if [[ \$EXIT_CODE -ne 0 && \$EXIT_CODE -ne 1 && \$EXIT_CODE -ne 3 ]]; then
        echo "ERROR: fusion doctor failed with exit code \$EXIT_CODE (non-validation error)" >&2
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

    def run  = run_tools  ? run_tools.tokenize(",")*.toUpperCase() : default_run_tools
    def skip = skip_tools.tokenize(",")*.toUpperCase()
    channel.fromList(run.findAll { it !in skip })
        .flatten()
        .branch { toolname ->
            TEST_BIN_SCRIPT:         toolname == "TEST_BIN_SCRIPT"
            TEST_CREATE_EMPTY_FILE:  toolname == "TEST_CREATE_EMPTY_FILE"
            TEST_CREATE_FILE:        toolname == "TEST_CREATE_FILE"
            TEST_CREATE_FOLDER:      toolname == "TEST_CREATE_FOLDER"
            TEST_FUSION_DOCTOR:      toolname == "TEST_FUSION_DOCTOR" || fusion
            TEST_GPU:                toolname == "TEST_GPU" && gpu
            TEST_IGNORED_FAIL:       toolname == "TEST_IGNORED_FAIL"
            TEST_INPUT:              toolname == "TEST_INPUT"
            TEST_MV_FILE:            toolname == "TEST_MV_FILE"
            TEST_MV_FOLDER_CONTENTS: toolname == "TEST_MV_FOLDER_CONTENTS"
            TEST_PASS_FILE:          toolname == "TEST_PASS_FILE"
            TEST_PASS_FOLDER:        toolname == "TEST_PASS_FOLDER"
            TEST_PUBLISH_FILE:       toolname == "TEST_PUBLISH_FILE"
            TEST_PUBLISH_FOLDER:     toolname == "TEST_PUBLISH_FOLDER"
            TEST_STAGE_REMOTE:       toolname == "TEST_STAGE_REMOTE"
            TEST_SUCCESS:            toolname == "TEST_SUCCESS"
            TEST_VAL_INPUT:          toolname == "TEST_VAL_INPUT"
        }
        .set { run_ch }

        channel
            .of("alpha", "beta", "gamma")
            .collectFile(name: 'sample.txt', newLine: true)
            .set { test_file }

        remote_file = params.remoteFile ? channel.fromPath(params.remoteFile, glob:false) : channel.empty()

        // Run tests
        TEST_SUCCESS(           run_ch.TEST_SUCCESS )
        TEST_CREATE_FILE(       run_ch.TEST_CREATE_FILE )
        TEST_CREATE_EMPTY_FILE( run_ch.TEST_CREATE_EMPTY_FILE )
        TEST_CREATE_FOLDER(     run_ch.TEST_CREATE_FOLDER )
        TEST_INPUT(             run_ch.TEST_INPUT, test_file )
        TEST_BIN_SCRIPT(        run_ch.TEST_BIN_SCRIPT )
        TEST_STAGE_REMOTE(      run_ch.TEST_STAGE_REMOTE, remote_file )
        TEST_PASS_FILE(         run_ch.TEST_PASS_FILE, TEST_CREATE_FILE.out.outfile )
        TEST_PASS_FOLDER(       run_ch.TEST_PASS_FOLDER, TEST_CREATE_FOLDER.out.outfolder )
        TEST_PUBLISH_FILE(      run_ch.TEST_PUBLISH_FILE )
        TEST_PUBLISH_FOLDER(    run_ch.TEST_PUBLISH_FOLDER )
        TEST_IGNORED_FAIL(      run_ch.TEST_IGNORED_FAIL )
        TEST_MV_FILE(           run_ch.TEST_MV_FILE )
        TEST_MV_FOLDER_CONTENTS(run_ch.TEST_MV_FOLDER_CONTENTS )
        TEST_VAL_INPUT(         run_ch.TEST_VAL_INPUT, "Hello World" )
        TEST_GPU(               run_ch.TEST_GPU, "dummy" )

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
}
