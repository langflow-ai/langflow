# This file is used by `lc-serve` to build the image. 
# Don't change the name of this file.

FROM jinawolf/serving-gateway:${version}

RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential libpq-dev

COPY . /appdir/

RUN pip install poetry==1.4.0 && cd /appdir && pip install . && \
    pip uninstall -y poetry && \
    apt-get remove --auto-remove -y build-essential libpq-dev && \
    apt-get autoremove && apt-get clean && rm -rf /var/lib/apt/lists/* && rm -rf /tmp/*

ENTRYPOINT [ "jina", "gateway", "--uses", "config.yml" ]