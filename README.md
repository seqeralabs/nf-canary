[![nf-test](https://github.com/adamrtalbot/nf-canary/actions/workflows/nf-test.yml/badge.svg)](https://github.com/adamrtalbot/nf-canary/actions/workflows/nf-test.yml)

# :bird: nf-canary

A minimal Nextflow workflow for testing infrastructure.

## Introduction

After setting up and deploying your infrastructure, you may need to test you can effectively run a Nextflow pipeline. Common issues include network problems, permissions and invalid paths. The aim of this pipeline is to run through a set of standard tasks and confirm they are able to work. By using simple tasks which test as few things as possible, we can isolate individual any problems that may be occurring and fix them.

This pipeline aims to be as simple as possible. Therefore it comes with no additional configuration and the user will need to configure the run for their own infrastructure.

All tests are in the `main.nf` file and aim to be as simple and legible as possible. If it is difficult to understand a test, please raise an issue.

## Usage

### Running locally

To run locally, you can simply run:

```
nextflow run adamrtalbot/nf-canary
```

This will execute on your local machine with default settings. All tests should pass here. If they do not something is incorrect about your Nextflow installation or configuration.

### Running on your infrastructure

Add the configuration for your infrastructure using the relevant configuration files as listed in [the Nextflow documentation](https://www.nextflow.io/docs/latest/config.html). You can then run the same pipeline but with the additional configuration to run on your set up.

### Skipping Tests

Each test can be skipped by name with the parameter `--skip`, e.g. `--skip TEST_INPUT`. Multiple can be specified with comma delimited values, e.g. `--skip TEST_CREATE_FILE,TEST_PASS_FILE`. Note, some tests depend on previous tests running so will be skipped if an upstream test does not run (or fails). All tests which are dependent on previous tests are listed here:

```yaml
TEST_CREATE_FILE:
  - TEST_PASS_FILE
```

### Interpreting the results

The code for each test includes a short comment explaining what it is aiming to test. If it fails, check the comment for what it was trying to achieve and compare that to the error message reported by Nextflow.

## Test Overview

### `TEST_SUCCESS`

This process should automatically succeed with exit status 0.

### `TEST_CREATE_FILE`

This process should create a file on the worker machine then move it to the working directory.

### `TEST_INPUT`

This process should retrieve a file from the working directory and read the contents on the worker machine.

### `TEST_STAGE_REMOTE`

_Note: This will only be enabled if the parameter `--remoteFile` is specified._

This process retrieves a file from a remote resource to the worker machine and reads the contents. This uses the URL defined in the parameter `--remoteFile`, e.g. to download this README:

```
nextflow run adamrtalbot/nf-canary --remoteFile 'https://raw.githubusercontent.com/adamrtalbot/nf-canary/main/README.md'
```

Use this parameter to point to a file that you wish to access when running

### `TEST_PASS_FILE`

This process stages a file from the working directory to the worker node, copies it and stages it back to the working directory.

### `TEST_PUBLISH_FILE`

This process creates a file on the worker machine, then writes that file to the publishDir directory. This is the by default written to an subfolder called `output` in the working directory.
