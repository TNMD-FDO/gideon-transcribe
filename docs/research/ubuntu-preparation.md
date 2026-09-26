# Preparing Ubuntu: Docker, the NVIDIA driver, the container toolkit

The install guide's Step 0 (v1.92.0) walks the three things the app needs from the operating system. The commands are the makers' own, read from their pages on 2026-09-26; this note keeps where each was read so the step can be checked again when a page moves.

## Docker Engine with the Compose plugin

Read from https://docs.docker.com/engine/install/ubuntu/ ("Install using the apt repository"). The repository is added as a deb822 source at `/etc/apt/sources.list.d/docker.sources` signed by `/etc/apt/keyrings/docker.asc`, the suite taken from `/etc/os-release`; the packages are `docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`; the check is `docker run hello-world`. The guide adds `usermod -aG docker` for the compose admin, which Docker documents under its post-install steps, and reads `docker compose version` as the check that the plugin is the one the app needs.

## The NVIDIA driver

Read from https://ubuntu.com/server/docs/how-to/graphics/install-nvidia-drivers/. For a server, `sudo ubuntu-drivers install --gpgpu` installs the recommended server driver; `sudo ubuntu-drivers list --gpgpu` lists the ones on offer (named `nvidia-driver-<version>-server`); a reboot follows and `nvidia-smi` is the check. The app's stack needs a driver of 570 or newer (`whisperx-pinned-stack.md`), which is why the guide says to pick a newer one from the list when the recommended driver is older.

## The NVIDIA container toolkit and CDI

Read from https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html: the repository key at `/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg`, the list file from `nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list`, the package `nvidia-container-toolkit` (the page pins a version in an environment variable; the guide takes the repository's current one, since the toolkit is a host package the app never pins), then `nvidia-ctk runtime configure --runtime=docker` and a Docker restart.

The CDI specification, read from https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html: `nvidia-ctk cdi generate --output=...` writes it and `nvidia-ctk cdi list` lists the device names it holds. NVIDIA's page writes the file under `/var/run/cdi/`; the guide writes it to `/etc/cdi/nvidia.yaml` so it survives a reboot, which the same page names as a location the runtime reads. The page says the `nvidia-cdi-refresh` service regenerates it when the toolkit or the driver is installed or upgraded, and that some changes still need the `generate` line run by hand, which is why the guide says to run it again after a driver upgrade and after a card is replaced.

## What `./transcribe install` checks

`nvidia-smi` for the driver, as before, and from v1.92.0 `nvidia-ctk cdi list` for a line beginning `nvidia.com/gpu=`; either missing is a note, and the install goes on without transcription.
