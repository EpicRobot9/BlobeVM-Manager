FROM ghcr.io/linuxserver/baseimage-kasmvnc:ubuntujammy

# set version label
ARG BUILD_DATE
ARG VERSION
LABEL build_version="[Mollomm1 Mod] Linuxserver.io version:- ${VERSION} Build-date:- ${BUILD_DATE}"
LABEL maintainer="mollomm1"

ARG DEBIAN_FRONTEND="noninteractive"

# prevent Ubuntu's firefox stub from being installed
COPY /root/etc/apt/preferences.d/firefox-no-snap /etc/apt/preferences.d/firefox-no-snap

COPY options.json /

COPY /root/ /

RUN \
  echo "**** install packages ****" && \
  add-apt-repository -y ppa:mozillateam/ppa && \
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y firefox jq wget && \
  chmod +x /install-de.sh && \
  /install-de.sh

RUN \
  chmod +x /installapps.sh && \
  /installapps.sh && \
  rm /installapps.sh

RUN \
  echo "**** cleanup ****" && \
  apt-get autoclean && \
  rm -rf \
    /config/.cache \
    /var/lib/apt/lists/* \
    /var/tmp/* \
    /tmp/*

# Copy wrapper into image and update desktop file so launches use wrapper
COPY root/usr-local/google-chrome-wrapper /usr/local/bin/google-chrome-wrapper
RUN \
  chmod 0755 /usr/local/bin/google-chrome-wrapper && \
  sed -i 's|Exec=/usr/bin/google-chrome-stable .*%U|Exec=/usr/local/bin/google-chrome-wrapper %U|' /usr/share/applications/google-chrome.desktop || true && \
  sed -i 's|Exec=/usr/bin/google-chrome-stable$|Exec=/usr/local/bin/google-chrome-wrapper|' /usr/share/applications/google-chrome.desktop || true && \
  sed -i 's|Exec=/usr/bin/google-chrome-stable --incognito|Exec=/usr/local/bin/google-chrome-wrapper --incognito|' /usr/share/applications/google-chrome.desktop || true
  
# ports and volumes
EXPOSE 3000
VOLUME /config
