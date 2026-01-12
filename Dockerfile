FROM kasmweb/chrome:1.18.0-rolling-daily

# set version label
ARG BUILD_DATE
ARG VERSION
LABEL build_version="[Mollomm1 Mod] Kasm Chrome version:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="mollomm1"

ARG DEBIAN_FRONTEND="noninteractive"

RUN \
  echo "**** Skipping package installation for kasmweb/chrome base image ****" && \
  echo "# Chrome and desktop environment already configured in base image"

RUN \
  echo "**** Skipping app installation for kasmweb/chrome base image ****" && \
  echo "# Apps already configured in base image - Chrome and desktop environment ready"

RUN \
  echo "**** cleanup ****" && \
  apt-get autoclean && \
  rm -rf \
    /config/.cache \
    /var/lib/apt/lists/* \
    /var/tmp/* \
    /tmp/*
  
# ports and volumes
EXPOSE 4901
VOLUME /config
