# WhisperX Installation Guide on Windows (Using WSL)

This guide outlines the steps to install and configure WhisperX on Windows using Windows Subsystem for Linux (WSL). It includes installations, configurations, and fixes to ensure a fully operational system with GPU acceleration.

---

## 1. Setting Up WSL and Conda

### Install WSL (if not already installed):
```bash
wsl --install
```

### Install Miniconda:
1. Download Miniconda:
   ```bash
   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
   ```
2. Install Miniconda:
   ```bash
   bash Miniconda3-latest-Linux-x86_64.sh
   ```
3. Initialize Conda:
   ```bash
   conda init
   source ~/.bashrc
   ```
4. Create a new environment:
   ```bash
   conda create --name whisperx python=3.10
   conda activate whisperx
   ```

---

## 2. Installing CUDA and cuDNN in WSL

### Install CUDA Toolkit:
1. Update the package manager:
   ```bash
   sudo apt update
   ```
2. Install the NVIDIA CUDA Toolkit:
   ```bash
   sudo apt install nvidia-cuda-toolkit -y
   ```
3. Verify CUDA installation:
   ```bash
   nvcc --version
   ```

### Install cuDNN:
1. Download cuDNN from the official NVIDIA website:
   - Version: cuDNN 8.x for CUDA 12.0

2. Extract the downloaded files:
   ```bash
   tar -xJvf cudnn-linux-x86_64-8.x.x_cuda12-archive.tar.xz
   ```
3. Copy files to the appropriate directories:
   ```bash
   sudo cp cudnn-linux-x86_64-8.x.x_cuda12-archive/include/cudnn*.h /usr/local/cuda/include/
   sudo cp cudnn-linux-x86_64-8.x.x_cuda12-archive/lib/libcudnn* /usr/local/cuda/lib64/
   sudo chmod a+r /usr/local/cuda/include/cudnn*.h /usr/local/cuda/lib64/libcudnn*
   ```
4. Update the library loader:
   ```bash
   sudo ldconfig
   ```
5. Verify installation:
   ```bash
   ldconfig -p | grep libcudnn
   ```

---

## 3. Install FFmpeg

WhisperX requires FFmpeg for audio file processing. Install it using:
```bash
sudo apt install ffmpeg -y
```

Verify the installation:
```bash
ffmpeg -version
```

---

## 4. Install WhisperX

1. Install WhisperX using pip:
   ```bash
   pip install whisperx
   ```

---

## 5. Export Conda Environment

Save the environment to a file for future use:
```bash
conda env export > environment.yml
```

To recreate the environment:
```bash
conda env create -f environment.yml
```

---

## Summary

1. Installed and configured WSL and Miniconda.
2. Installed CUDA Toolkit and cuDNN for CUDA 12.0.
3. Installed FFmpeg for audio processing.
4. Installed compatible versions of PyTorch and torchaudio.
5. Installed WhisperX and configured the scripts (e.g., added `--no_align` flag). # it's not nessesery at the moment
6. Exported the Conda environment to `environment.yml`.

The system is now fully operational with GPU acceleration in the WSL environment. For further configurations or optimizations, feel free to reach out! 🚀

writed by @mp3pintyo