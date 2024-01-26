[![nf-test](https://github.com/seqeralabs/nf-canary/actions/workflows/test.yml/badge.svg)](https://github.com/seqeralabs/nf-canary/actions/workflows/test.yml)

# :bird: nf-canary

A lightweight Nextflow workflow designed for testing infrastructure.

## Introduction

After configuring and deploying your infrastructure, validating the functionality of a Nextflow pipeline is crucial. Common issues include network problems, permission discrepancies, and invalid paths. The purpose of this pipeline is to execute a series of straightforward tasks to ensure they function properly. By employing simple tasks that test specific functionalities, we can pinpoint and resolve individual issues effectively.

This pipeline is intentionally minimalistic, arriving with no additional configuration. Users are required to tailor the run settings to their specific infrastructure.

All tests are consolidated in the `main.nf` file, prioritizing simplicity and readability. If any test is challenging to comprehend, please raise an issue.

## Usage

### Running Locally

To execute locally, use the following command:

```bash
nextflow run seqeralabs/nf-canary
```

This will run on your local machine with default settings. Successful execution of all tests indicates a correctly configured Nextflow installation. Any failures suggest potential issues with your configuration.

### Running on Your Infrastructure

Configure your infrastructure using the appropriate configuration files listed in [the Nextflow documentation](https://www.nextflow.io/docs/latest/config.html). Run the pipeline with the additional configuration to execute it on your setup.

### Output Directory

nf-canary adheres to the `--outdir` convention established by [nf-core](https://nf-co.re/) to determine the output file destination. If not specified, output files are written to the work directory under a subfolder named `outputs`.

### Skipping Tests

Skip individual tests by name using the `--skip` parameter, e.g., `--skip TEST_INPUT`. Multiple tests can be specified with comma-delimited values, e.g., `--skip TEST_CREATE_FILE,TEST_PASS_FILE`. The parameter is case-insensitive.

### Selectively Running Tests

By default, all tests are executed. However, you can selectively run a specific test with the `--run` parameter, e.g., `--run TEST_INPUT`. When using this parameter, only the selected tests will run. Multiple tests can be specified with comma-delimited values, e.g., `--run TEST_CREATE_FILE,TEST_PASS_FILE`. Case insensitive.

### Note on Test Dependency

Certain tests depend on the successful execution of previous tests and will be skipped if an upstream test fails. The dependencies for each test are listed below:

```yaml
TEST_CREATE_FILE:
  - TEST_PASS_FILE
TEST_CREATE_FOLDER:
  - TEST_PASS_FOLDER
```

### Interpreting the Results

Each test includes a brief comment explaining its purpose. In case of failure, review the comment to understand the intended outcome and compare it to the error message reported by Nextflow.

## Test Overview

### `TEST_SUCCESS`

This process should succeed automatically with exit status 0.

### `TEST_CREATE_FILE`

This process creates a file on the worker machine and then moves it to the working directory.

### `TEST_CREATE_FOLDER`

This process creates a folder in the working directory.

### `TEST_INPUT`

This process retrieves a file from the working directory and reads its contents on the worker machine.

### `TEST_BIN_SCRIPT`

Tests a shell script in the `bin/` directory that creates a single file.

### `TEST_STAGE_REMOTE`

*Note: Enabled only if the parameter `--remoteFile` is specified.*

This process retrieves a file from a remote resource to the worker machine and reads its contents. Use the `--remoteFile` parameter, e.g., to download this README:

```bash
nextflow run seqeralabs/nf-canary --remoteFile 'https://raw.githubusercontent.com/seqeralabs/nf-canary/main/README.md'
```

Use this parameter to specify a file to access during runtime.

### `TEST_PASS_FILE`

This process stages a file from the working directory to the worker node, copies it, and stages it back to the working directory.

### `TEST_PASS_FOLDER`

This process stages a folder from the working directory to the worker node, copies it, and stages it back to the working directory.

### `TEST_PUBLISH_FILE`

This process creates a file on the worker machine and writes it to the publishDir directory. By default, this is written to a subfolder called `output` in the working directory, but it can be overridden using the `--outdir` parameter. Use this to demonstrate the ability to publish to the relevant output directory.

### `TEST_PUBLISH_FOLDER`

This process creates a folder on the worker machine and writes it to the publishDir directory. By default, this is written to a subfolder called `output` in the working directory, but it can be overridden using the `--outdir` parameter. Use this to demonstrate the ability to publish to the relevant output directory.

### `TEST_IGNORED_FAIL`

This process should fail immediately but be ignored using the default configuration.

### `TEST_MV_FILE`

Tests moving a file within the working directory.

### `TEST_MV_FOLDER_CONTENTS`

Tests moving the contents of a folder to a new folder within the working directory.
```
