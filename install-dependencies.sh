#!/usr/bin/env bash

debian_packages=(
    libldap2-dev
    libsasl2-dev
    libssl-dev
    python3-dev
)

redhat_packages=(
    python3-devel
    openldap-devel
)

function guess_package_manager() {
    # Debian or Ubuntu.
    if apt --version &>/dev/null; then
        echo "deb"
    fi

    # RedHat.
    if yum --version &>/dev/null; then
        echo "yum"
    fi
}

install_package_dependencies() {
    local packageManager=$(guess_package_manager)

    if [[ "$packageManager" == "deb" ]]; then
        sudo apt install "${debian_packages[@]}"
    elif [[ "$packageManager" == "yum" ]]; then
        sudo yum install "${redhat_packages[@]}"
    fi
}

install_module_dependencies() {
    pip3 install -r requirements.txt
}

install_package_dependencies
install_module_dependencies
