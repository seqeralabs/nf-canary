process TEST_SUCCESS {
    /*
    This process should automatically succeed
    */

    script:
    """
    exit 0
    """
}

process TEST_CREATE_FILE {
    /*
    Creates a file on the worker node which is uploaded to the working directory.
    */

    output:
        path("*.txt"), emit: outfile

    """
    touch test.txt
    """
}

process TEST_CREATE_FOLDER {
    /*
    Creates a file on the worker node which is uploaded to the working directory.
    */

    output:
        path("test"), type: 'dir', emit: outfolder

    """
    mkdir -p test
    touch test/test1.txt
    touch test/test2.txt
    """
}

process TEST_INPUT {
    /*
    Stages a file from the working directory to the worker node.
    */

    input:
        path input

    output:
        stdout

    """
    cat $input
    """
}

process TEST_BIN_SCRIPT {
    /*
    Runs a script from the bin/ directory
    */

    output:
        path("*.txt")

    """
    bash run.sh
    """
}

process TEST_STAGE_REMOTE {
    /*
    Stages a file from a remote file to the worker node.
    */

    input:
        path input

    output:
        stdout

    """
    cat $input
    """
}

process TEST_PASS_FILE {
    /*
    Stages a file from the working directory to the worker node, copies it and stages it back to the working directory.
    */

    input:
        path input

    output:
        path "out.txt", emit: outfile

    """
    cp "$input" "out.txt"
    """
}

process TEST_PASS_FOLDER {
    /*
    Stages a folder from the working directory to the worker node, copies it and stages it back to the working directory.
    */

    input:
        path input

    output:
        path "out", type: 'dir'   , emit: outfolder
        path "out/*", type: 'file', emit: outfile

    """
    cp -rL $input out
    """
}

process TEST_PUBLISH_FILE {
    /*
    Creates a file on the worker node and uploads to the publish directory.
    */


    publishDir { params.outdir ?: file(workflow.workDir).resolve("outputs").toUriString()  }, mode: 'copy'

    output:
        path("*.txt")

    """
    touch test.txt
    """
}

process TEST_PUBLISH_FOLDER {
    /*
    Creates a file on the worker node and uploads to the publish directory.
    */

    publishDir { params.outdir ?: file(workflow.workDir).resolve("outputs").toUriString()  }, mode: 'copy'

    output:
        path("test", type: 'dir')

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

    """
    exit 1
    """
}

process TEST_MV_FILE {
    /*
    This process moves a file within a working directory.
    */

    input:
        path input

    output:
        path "output.txt"

    """
    mv $input output.txt
    """

}

process TEST_MV_FOLDER_CONTENTS {
    /*
    Moves the contents of a folder from within a folder
    */

    input:
        path input

    output:
        path "out", type: 'dir'   , emit: outfolder
        path "out/*", type: 'file', emit: outfile

    """
    mkdir -p out
    mv $input/* out/
    """
}

workflow {

    // Create test file on head node
    Channel
        .of("alpha", "beta", "gamma")
        .collectFile(name: 'sample.txt', newLine: true)
        .set { test_file }

    remote_file = params.remoteFile ? Channel.fromPath(params.remoteFile) : Channel.empty()

    // Run tests
    TEST_SUCCESS()
    TEST_CREATE_FILE()
    TEST_CREATE_FOLDER()
    TEST_INPUT(test_file)
    TEST_BIN_SCRIPT()
    TEST_STAGE_REMOTE(remote_file)
    TEST_PASS_FILE(TEST_CREATE_FILE.out.outfile)
    TEST_PASS_FOLDER(TEST_CREATE_FOLDER.out.outfolder)
    TEST_PUBLISH_FILE()
    TEST_PUBLISH_FOLDER()
    TEST_IGNORED_FAIL()
}
