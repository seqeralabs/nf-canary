def selectTool(toolname) {
    def inRunParam = ( params.run ? params.run.split(',').any{ runName -> "${runName.toUpperCase()}".contains(toolname) } : true )
    def inSkipParam = (!params.skip.split(',').any{ runName -> "${runName.toUpperCase()}".contains(toolname) } )
    return inRunParam && inSkipParam
}

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

workflow NF_CANARY {

    main:
        // Create dummy channel for inputs
        Channel.of('dummy')
            .set { dummy_ch }

        Channel
            .of("alpha", "beta", "gamma")
            .collectFile(name: 'sample.txt', newLine: true)
            .set { test_file }

        remote_file = params.remoteFile ? Channel.fromPath(params.remoteFile, glob:false) : Channel.empty()

        // Run tests
        TEST_SUCCESS(           dummy_ch.filter { selectTool('TEST_SUCCESS'           ) } )
        TEST_CREATE_FILE(       dummy_ch.filter { selectTool('TEST_CREATE_FILE'       )} )
        TEST_CREATE_EMPTY_FILE( dummy_ch.filter { selectTool('TEST_CREATE_EMPTY_FILE' ) })
	    TEST_CREATE_FOLDER(     dummy_ch.filter { selectTool('TEST_CREATE_FOLDER'     ) })
        TEST_INPUT(             dummy_ch.filter { selectTool('TEST_INPUT'             ) }, test_file)
        TEST_BIN_SCRIPT(        dummy_ch.filter { selectTool('TEST_BIN_SCRIPT'        ) })
        TEST_STAGE_REMOTE(      dummy_ch.filter { selectTool('TEST_STAGE_REMOTE'      ) }, remote_file)
        TEST_PASS_FILE(         dummy_ch.filter { selectTool('TEST_PASS_FILE'         ) }, TEST_CREATE_FILE.out.outfile)
        TEST_PASS_FOLDER(       dummy_ch.filter { selectTool('TEST_PASS_FOLDER'       ) }, TEST_CREATE_FOLDER.out.outfolder)
        TEST_PUBLISH_FILE(      dummy_ch.filter { selectTool('TEST_PUBLISH_FILE'      ) })
        TEST_PUBLISH_FOLDER(    dummy_ch.filter { selectTool('TEST_PUBLISH_FOLDER'    ) })
        TEST_IGNORED_FAIL(      dummy_ch.filter { selectTool('TEST_IGNORED_FAIL'      ) })
        TEST_MV_FILE(           dummy_ch.filter { selectTool('TEST_MV_FILE'           ) })
        TEST_MV_FOLDER_CONTENTS(dummy_ch.filter { selectTool('TEST_MV_FOLDER_CONTENTS') })
        TEST_VAL_INPUT(         dummy_ch.filter { selectTool('TEST_VAL_INPUT'         ) }, "Hello World")

        TEST_GPU(               dummy_ch.filter { params.gpu && selectTool("TEST_GPU" ) }, "dummy")

        // POC of emitting the channel
        Channel.empty()
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
                TEST_GPU.out
            )
            .set { ch_out }

    emit:
        out = ch_out
}

workflow {
    NF_CANARY()
}
