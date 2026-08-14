FROM codercom/code-server:latest

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /opt/student-template/requirements.txt
RUN python3 -m pip install --break-system-packages --no-cache-dir -r /opt/student-template/requirements.txt

COPY starter /opt/student-template/starter
COPY start.sh /usr/local/bin/student-workspace-start
RUN chmod +x /usr/local/bin/student-workspace-start \
    && chown -R coder:coder /opt/student-template

USER coder
WORKDIR /home/coder/project
EXPOSE 8080 8000
ENTRYPOINT ["/usr/local/bin/student-workspace-start"]
