# Initial stab at a devcontainer for the RAFTS project
FROM infrastructurebuilder/almabase:0.3
RUN dnf install -y sudo
RUN useradd -U rafts
RUN usermod -aG wheel rafts
RUN echo '%wheel ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/wheel
RUN chmod 0440 /etc/sudoers.d/wheel 
RUN <<EOF
#  dnf -y update && dnf -y groupinstall "Development Tools"  && dnf -y install gcc-gfortran
  dnf -y update
EOF
  
USER rafts
ENV HOME=/home/rafts

RUN <<EOF
  curl -LsSf https://astral.sh/uv/install.sh | sh -s --
  echo 'eval "$(uv generate-shell-completion bash)"' >> ~/.bashrc
  curl -LsSf https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh
  bash /tmp/miniconda.sh -b 
  rm /tmp/miniconda.sh
  echo 'export PATH=$HOME/miniconda3/bin:$PATH' >> ~/.bashrc
  echo 'export CONDA_AUTO_UPDATE_CONDA=false' >> ~/.bashrc
  echo 'export CONDA_PKGS_DIRS=/$HOME/miniconda3/pkgs' >> ~/.bashrc
  echo 'export CONDA_ENV_PATH=/$HOME/miniconda3/envs' >> ~/.bashrc
  # /opt/conda/bin/conda clean -ya
  # /opt/conda/bin/conda config --set auto_update_conda False
  # /opt/conda/bin/conda config --set show_channel_urls True
  # /opt/conda/bin/conda config --add channels conda-forge
  # /opt/conda/bin/conda config --add channels bioconda
  # /opt/conda/bin/conda config --add channels defaults
  # /opt/conda/bin/conda config --add channels r
EOF
