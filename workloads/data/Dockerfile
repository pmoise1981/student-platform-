FROM quay.io/jupyter/pyspark-notebook:latest

USER root
RUN pip install --no-cache-dir boto3 minio
COPY starter /opt/student-template/starter
COPY start.sh /usr/local/bin/student-data-start
RUN chmod +x /usr/local/bin/student-data-start \
    && chown -R ${NB_UID}:${NB_GID} /opt/student-template

USER ${NB_UID}
WORKDIR /home/jovyan/work
ENTRYPOINT ["/usr/local/bin/student-data-start"]
