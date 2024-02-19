exports.id = 439;
exports.ids = [439];
exports.modules = {

/***/ 356:
/***/ ((module, __unused_webpack_exports, __webpack_require__) => {

/* provided dependency */ var console = __webpack_require__(5108);
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
var __publicField = (obj, key, value) => {
  __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
  return value;
};
var YouTube_exports = {};
__export(YouTube_exports, {
  default: () => YouTube
});
module.exports = __toCommonJS(YouTube_exports);
var import_react = __toESM(__webpack_require__(7294));
var import_utils = __webpack_require__(8045);
var import_patterns = __webpack_require__(1776);
const SDK_URL = "https://www.youtube.com/iframe_api";
const SDK_GLOBAL = "YT";
const SDK_GLOBAL_READY = "onYouTubeIframeAPIReady";
const MATCH_PLAYLIST = /[?&](?:list|channel)=([a-zA-Z0-9_-]+)/;
const MATCH_USER_UPLOADS = /user\/([a-zA-Z0-9_-]+)\/?/;
const MATCH_NOCOOKIE = /youtube-nocookie\.com/;
const NOCOOKIE_HOST = "https://www.youtube-nocookie.com";
class YouTube extends import_react.Component {
  constructor() {
    super(...arguments);
    __publicField(this, "callPlayer", import_utils.callPlayer);
    __publicField(this, "parsePlaylist", (url) => {
      if (url instanceof Array) {
        return {
          listType: "playlist",
          playlist: url.map(this.getID).join(",")
        };
      }
      if (MATCH_PLAYLIST.test(url)) {
        const [, playlistId] = url.match(MATCH_PLAYLIST);
        return {
          listType: "playlist",
          list: playlistId.replace(/^UC/, "UU")
        };
      }
      if (MATCH_USER_UPLOADS.test(url)) {
        const [, username] = url.match(MATCH_USER_UPLOADS);
        return {
          listType: "user_uploads",
          list: username
        };
      }
      return {};
    });
    __publicField(this, "onStateChange", (event) => {
      const { data } = event;
      const { onPlay, onPause, onBuffer, onBufferEnd, onEnded, onReady, loop, config: { playerVars, onUnstarted } } = this.props;
      const { UNSTARTED, PLAYING, PAUSED, BUFFERING, ENDED, CUED } = window[SDK_GLOBAL].PlayerState;
      if (data === UNSTARTED)
        onUnstarted();
      if (data === PLAYING) {
        onPlay();
        onBufferEnd();
      }
      if (data === PAUSED)
        onPause();
      if (data === BUFFERING)
        onBuffer();
      if (data === ENDED) {
        const isPlaylist = !!this.callPlayer("getPlaylist");
        if (loop && !isPlaylist) {
          if (playerVars.start) {
            this.seekTo(playerVars.start);
          } else {
            this.play();
          }
        }
        onEnded();
      }
      if (data === CUED)
        onReady();
    });
    __publicField(this, "mute", () => {
      this.callPlayer("mute");
    });
    __publicField(this, "unmute", () => {
      this.callPlayer("unMute");
    });
    __publicField(this, "ref", (container) => {
      this.container = container;
    });
  }
  componentDidMount() {
    this.props.onMount && this.props.onMount(this);
  }
  getID(url) {
    if (!url || url instanceof Array || MATCH_PLAYLIST.test(url)) {
      return null;
    }
    return url.match(import_patterns.MATCH_URL_YOUTUBE)[1];
  }
  load(url, isReady) {
    const { playing, muted, playsinline, controls, loop, config, onError } = this.props;
    const { playerVars, embedOptions } = config;
    const id = this.getID(url);
    if (isReady) {
      if (MATCH_PLAYLIST.test(url) || MATCH_USER_UPLOADS.test(url) || url instanceof Array) {
        this.player.loadPlaylist(this.parsePlaylist(url));
        return;
      }
      this.player.cueVideoById({
        videoId: id,
        startSeconds: (0, import_utils.parseStartTime)(url) || playerVars.start,
        endSeconds: (0, import_utils.parseEndTime)(url) || playerVars.end
      });
      return;
    }
    (0, import_utils.getSDK)(SDK_URL, SDK_GLOBAL, SDK_GLOBAL_READY, (YT) => YT.loaded).then((YT) => {
      if (!this.container)
        return;
      this.player = new YT.Player(this.container, {
        width: "100%",
        height: "100%",
        videoId: id,
        playerVars: {
          autoplay: playing ? 1 : 0,
          mute: muted ? 1 : 0,
          controls: controls ? 1 : 0,
          start: (0, import_utils.parseStartTime)(url),
          end: (0, import_utils.parseEndTime)(url),
          origin: window.location.origin,
          playsinline: playsinline ? 1 : 0,
          ...this.parsePlaylist(url),
          ...playerVars
        },
        events: {
          onReady: () => {
            if (loop) {
              this.player.setLoop(true);
            }
            this.props.onReady();
          },
          onPlaybackRateChange: (event) => this.props.onPlaybackRateChange(event.data),
          onPlaybackQualityChange: (event) => this.props.onPlaybackQualityChange(event),
          onStateChange: this.onStateChange,
          onError: (event) => onError(event.data)
        },
        host: MATCH_NOCOOKIE.test(url) ? NOCOOKIE_HOST : void 0,
        ...embedOptions
      });
    }, onError);
    if (embedOptions.events) {
      console.warn("Using `embedOptions.events` will likely break things. Use ReactPlayer\u2019s callback props instead, eg onReady, onPlay, onPause");
    }
  }
  play() {
    this.callPlayer("playVideo");
  }
  pause() {
    this.callPlayer("pauseVideo");
  }
  stop() {
    if (!document.body.contains(this.callPlayer("getIframe")))
      return;
    this.callPlayer("stopVideo");
  }
  seekTo(amount, keepPlaying = false) {
    this.callPlayer("seekTo", amount);
    if (!keepPlaying && !this.props.playing) {
      this.pause();
    }
  }
  setVolume(fraction) {
    this.callPlayer("setVolume", fraction * 100);
  }
  setPlaybackRate(rate) {
    this.callPlayer("setPlaybackRate", rate);
  }
  setLoop(loop) {
    this.callPlayer("setLoop", loop);
  }
  getDuration() {
    return this.callPlayer("getDuration");
  }
  getCurrentTime() {
    return this.callPlayer("getCurrentTime");
  }
  getSecondsLoaded() {
    return this.callPlayer("getVideoLoadedFraction") * this.getDuration();
  }
  render() {
    const { display } = this.props;
    const style = {
      width: "100%",
      height: "100%",
      display
    };
    return /* @__PURE__ */ import_react.default.createElement("div", { style }, /* @__PURE__ */ import_react.default.createElement("div", { ref: this.ref }));
  }
}
__publicField(YouTube, "displayName", "YouTube");
__publicField(YouTube, "canPlay", import_patterns.canPlay.youtube);


/***/ })

};
;