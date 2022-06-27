FROM ubuntu:focal

# install various supporting components for installation
RUN apt-get update
RUN apt-get install --yes curl apt-transport-https ca-certificates curl gnupg2 lsb-release software-properties-common

# install the GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null
RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 3FA7E0328081BFF6A14DA29AA6A19B38D3D831EF

# install some basic Linux components
RUN apt-get update && apt-get install --yes gcc libkrb5-dev libpq-dev sudo openssh-client gh vim net-tools

# workaround for wrong path in .gitconfig
RUN ln -s /usr/bin/gh /usr/local/bin/gh

# set up a non-root developer user
ARG USERNAME=serenityprod
RUN useradd -m $USERNAME
RUN echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME
RUN usermod --shell /bin/bash $USERNAME