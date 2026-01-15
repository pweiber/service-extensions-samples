# syntax=docker/dockerfile:1

# Base development image
FROM launcher.gcr.io/google/ubuntu2204:latest AS dev

# Update and upgrade the system
RUN apt-get update && apt-get upgrade -y && apt-get autoremove -y

# Install necessary dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    openssl \
    git \
    python3-distutils \
    clang \
    libstdc++6 \
    openjdk-21-jdk \
    libicu70 \
    curl \
    wget \
	build-essential

# Install the latest Go version
RUN wget https://go.dev/dl/go1.22.1.linux-amd64.tar.gz && \
    rm -rf /usr/local/go && \
    tar -C /usr/local -xzf go1.22.1.linux-amd64.tar.gz && \
    rm go1.22.1.linux-amd64.tar.gz

# Add Go to PATH
ENV PATH=$PATH:/usr/local/go/bin

# Add GitHub's SSL certificate to trusted certificates
ARG cert_location=/usr/local/share/ca-certificates
RUN mkdir -p ${cert_location} && \
    openssl s_client -showcerts -connect github.com:443 </dev/null 2>/dev/null | \
    openssl x509 -outform PEM > ${cert_location}/github.crt && \
    update-ca-certificates

# Create a non-root user for better security
RUN useradd -ms /bin/bash developer

# Set environment variables for the developer user
ENV GOPATH=/home/developer/go
ENV PATH="${PATH}:/home/developer/go/bin"

# Switch to the non-root user
USER developer

# Set the working directory inside the container
WORKDIR /home/developer/workspace

# Install Bazelisk using Go (as 'developer' user)
RUN go install github.com/bazelbuild/bazelisk@latest

# Verify Bazelisk installation
RUN bazelisk --version

EXPOSE 8443 8181 8000

# Default command to provide an interactive shell
CMD ["/bin/bash"]