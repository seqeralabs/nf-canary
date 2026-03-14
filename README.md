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

### Overriding default container

The container is specified by the `container` parameter, which defaults to `quay.io/biocontainers/ubuntu:24.04`. If you wish to use a different container, you can specify an alternative using the --container parameter.

```nextflow
params.container = 'docker.io/ubuntu:24.04'
```

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

### `TEST_CREATE_EMPTY_FILE`

This process creates an empty file on the worker machine and then moves it to the working directory.

### `TEST_CREATE_FOLDER`

This process creates a folder in the working directory.

### `TEST_INPUT`

This process retrieves a file from the working directory and reads its contents on the worker machine.

### `TEST_BIN_SCRIPT`

Tests a shell script in the `bin/` directory that creates a single file.

### `TEST_STAGE_REMOTE`

_Note: Enabled only if the parameter `--remoteFile` is specified._

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

### `TEST_VAL_INPUT`

Test a process can accept a value as input.

### `TEST_GPU`

_Note: Enabled only if the parameter `--gpu` is specified._

This process tests the ability to use a GPU. It uses the `pytorch` conda environment to test CUDA is available and working. This is disabled by default as it requires a GPU to be available which may not be true.

### `TEST_FUSION_DOCTOR`

_Note: Enabled only if the parameter `--fusion` is specified (or set to `true` by a profile)._

This process runs the `fusion doctor` diagnostics tool to validate the Fusion filesystem configuration. It checks system requirements (e.g. kernel version, memory, disk space, etc.), FUSE device availability, and cloud bucket accessibility among others. The process produces a JSON diagnostic report published to `${outdir}/fusion/`.

#### Fusion Profiles

Use a built-in profile to enable Fusion validation with predefined thresholds:

```bash
nextflow run seqeralabs/nf-canary -profile fusion_aws_recommended
```

> [!TIP]
>
> **If in doubt, start with the `recommended` tier:**
>
> 1. Choose `low` for small workloads or quick smoke tests, and `high` for large-scale production with big datasets.
> 2. Choose `recommended` to match Seqera's documented minimum requirements for production workloads with Fusion.
> 3. Choose `high` (or a custom threshold of 400 GB+ storage) if your pipeline processes files larger than 100 GB.

##### AWS

> [!NOTE]
>
> Seqera Platform will auto-select NVMe-based instance families when Fusion is enabled (e.g. `m6id`, `c6id`, `r6id`) and the "Fast instance storage" toggle is active in the CE settings. Fusion can also work without NVMe instances, but in this case the EBS disk shall be bumped to 100 GB (`gp3`, 325 MB/s); this is what the `low` profile validates.

| Profile                  | Disk   | Memory | Kernel | Based on            |
| ------------------------ | ------ | ------ | ------ | ------------------- |
| `fusion_aws_low`         | 100 GB | 4 GB   | 5.10+  | EBS gp3 (no NVMe)   |
| `fusion_aws_recommended` | 200 GB | 8 GB   | 5.10+  | Seqera docs minimum |
| `fusion_aws_high`        | 474 GB | 16 GB  | 5.10+  | m6id.2xlarge NVMe   |

**Google Cloud**

> [!NOTE]
>
> Seqera Platform auto-selects families supporting local SSDs (e.g. `n2`, `c2`, `n2d`) and provisions a 375 GB NVMe SSD per job.

| Profile                     | Disk   | Memory | Kernel | Based on            |
| --------------------------- | ------ | ------ | ------ | ------------------- |
| `fusion_google_low`         | 50 GB  | 4 GB   | 5.15+  | GCP persistent disk |
| `fusion_google_recommended` | 375 GB | 8 GB   | 5.15+  | 1x local NVMe SSD   |
| `fusion_google_high`        | 750 GB | 16 GB  | 5.15+  | 2x local NVMe SSDs  |

##### Azure

> [!note]
>
> Unlike AWS and Google Cloud, there is no auto-selection: the user must pick the VM size. Seqera recommends E-series with a `d` suffix (e.g. `Standard_E8d_v5`, `Standard_E16d_v5`).

| Profile                    | Disk   | Memory | Kernel | Based on                     |
| -------------------------- | ------ | ------ | ------ | ---------------------------- |
| `fusion_azure_low`         | 75 GB  | 4 GB   | 5.15+  | `Standard_E2d_v5` temp disk  |
| `fusion_azure_recommended` | 300 GB | 8 GB   | 5.15+  | `Standard_E8d_v5` temp disk  |
| `fusion_azure_high`        | 600 GB | 16 GB  | 5.15+  | `Standard_E16d_v5` temp disk |

#### Caveats

In AWS Batch, the Seqera Platform UI allows selecting instance families (e.g. `m6id`) but not specific sizes. Small instances in an otherwise valid family may not meet the `recommended` disk threshold. For example, on AWS the `m6id` family NVMe ranges from 118 GB (`.large`) to 1,900 GB (`.8xlarge`), with only `.xlarge` and above meeting the 200 GB threshold.

If `fusion doctor` reports a disk requirement failure, request more CPUs/memory to get a larger instance, or use the `low` profile for small tasks.

#### Custom Requirements

You can override the default requirements using command-line parameters:

```bash
nextflow run seqeralabs/nf-canary \
    --fusion \
    --fusion_kernel_version_min "5.10" \
    --fusion_memory_capacity_gb_min 8 \
    --fusion_disk_capacity_gb_min 100
```

Available parameters:

- `--fusion_kernel_version_min` - Minimum Linux kernel version (e.g., "5.10")
- `--fusion_memory_capacity_gb_min` - Minimum memory in GB (e.g., 8)
- `--fusion_disk_capacity_gb_min` - Minimum disk space in GB (e.g., 100)
- `--fusion_cache_path` - Path for Fusion cache directory (default: `/tmp`)
- `--fusion_read_write_buckets` - Comma-separated list of read-write bucket URIs
- `--fusion_read_only_buckets` - Comma-separated list of read-only bucket URIs
