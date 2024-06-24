exports.id = 458;
exports.ids = [458];
exports.modules = {

/***/ 688:
/***/ ((module, __unused_webpack_exports, __webpack_require__) => {

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
var FilePlayer_exports = {};
__export(FilePlayer_exports, {
  default: () => FilePlayer
});
module.exports = __toCommonJS(FilePlayer_exports);
var import_react = __toESM(__webpack_require__(6540));
var import_utils = __webpack_require__(5635);
var import_patterns = __webpack_require__(327);
const HAS_NAVIGATOR = typeof navigator !== "undefined";
const IS_IPAD_PRO = HAS_NAVIGATOR && navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
const IS_IOS = HAS_NAVIGATOR && (/iPad|iPhone|iPod/.test(navigator.userAgent) || IS_IPAD_PRO) && !window.MSStream;
const IS_SAFARI = HAS_NAVIGATOR && /^((?!chrome|android).)*safari/i.test(navigator.userAgent) && !window.MSStream;
const HLS_SDK_URL = "https://cdn.jsdelivr.net/npm/hls.js@VERSION/dist/hls.min.js";
const HLS_GLOBAL = "Hls";
const DASH_SDK_URL = "https://cdnjs.cloudflare.com/ajax/libs/dashjs/VERSION/dash.all.min.js";
const DASH_GLOBAL = "dashjs";
const FLV_SDK_URL = "https://cdn.jsdelivr.net/npm/flv.js@VERSION/dist/flv.min.js";
const FLV_GLOBAL = "flvjs";
const MATCH_DROPBOX_URL = /www\.dropbox\.com\/.+/;
const MATCH_CLOUDFLARE_STREAM = /https:\/\/watch\.cloudflarestream\.com\/([a-z0-9]+)/;
const REPLACE_CLOUDFLARE_STREAM = "https://videodelivery.net/{id}/manifest/video.m3u8";
class FilePlayer extends import_react.Component {
  constructor() {
    super(...arguments);
    // Proxy methods to prevent listener leaks
    __publicField(this, "onReady", (...args) => this.props.onReady(...args));
    __publicField(this, "onPlay", (...args) => this.props.onPlay(...args));
    __publicField(this, "onBuffer", (...args) => this.props.onBuffer(...args));
    __publicField(this, "onBufferEnd", (...args) => this.props.onBufferEnd(...args));
    __publicField(this, "onPause", (...args) => this.props.onPause(...args));
    __publicField(this, "onEnded", (...args) => this.props.onEnded(...args));
    __publicField(this, "onError", (...args) => this.props.onError(...args));
    __publicField(this, "onPlayBackRateChange", (event) => this.props.onPlaybackRateChange(event.target.playbackRate));
    __publicField(this, "onEnablePIP", (...args) => this.props.onEnablePIP(...args));
    __publicField(this, "onDisablePIP", (e) => {
      const { onDisablePIP, playing } = this.props;
      onDisablePIP(e);
      if (playing) {
        this.play();
      }
    });
    __publicField(this, "onPresentationModeChange", (e) => {
      if (this.player && (0, import_utils.supportsWebKitPresentationMode)(this.player)) {
        const { webkitPresentationMode } = this.player;
        if (webkitPresentationMode === "picture-in-picture") {
          this.onEnablePIP(e);
        } else if (webkitPresentationMode === "inline") {
          this.onDisablePIP(e);
        }
      }
    });
    __publicField(this, "onSeek", (e) => {
      this.props.onSeek(e.target.currentTime);
    });
    __publicField(this, "mute", () => {
      this.player.muted = true;
    });
    __publicField(this, "unmute", () => {
      this.player.muted = false;
    });
    __publicField(this, "renderSourceElement", (source, index) => {
      if (typeof source === "string") {
        return /* @__PURE__ */ import_react.default.createElement("source", { key: index, src: source });
      }
      return /* @__PURE__ */ import_react.default.createElement("source", { key: index, ...source });
    });
    __publicField(this, "renderTrack", (track, index) => {
      return /* @__PURE__ */ import_react.default.createElement("track", { key: index, ...track });
    });
    __publicField(this, "ref", (player) => {
      if (this.player) {
        this.prevPlayer = this.player;
      }
      this.player = player;
    });
  }
  componentDidMount() {
    this.props.onMount && this.props.onMount(this);
    this.addListeners(this.player);
    const src = this.getSource(this.props.url);
    if (src) {
      this.player.src = src;
    }
    if (IS_IOS || this.props.config.forceDisableHls) {
      this.player.load();
    }
  }
  componentDidUpdate(prevProps) {
    if (this.shouldUseAudio(this.props) !== this.shouldUseAudio(prevProps)) {
      this.removeListeners(this.prevPlayer, prevProps.url);
      this.addListeners(this.player);
    }
    if (this.props.url !== prevProps.url && !(0, import_utils.isMediaStream)(this.props.url) && !(this.props.url instanceof Array)) {
      this.player.srcObject = null;
    }
  }
  componentWillUnmount() {
    this.player.removeAttribute("src");
    this.removeListeners(this.player);
    if (this.hls) {
      this.hls.destroy();
    }
  }
  addListeners(player) {
    const { url, playsinline } = this.props;
    player.addEventListener("play", this.onPlay);
    player.addEventListener("waiting", this.onBuffer);
    player.addEventListener("playing", this.onBufferEnd);
    player.addEventListener("pause", this.onPause);
    player.addEventListener("seeked", this.onSeek);
    player.addEventListener("ended", this.onEnded);
    player.addEventListener("error", this.onError);
    player.addEventListener("ratechange", this.onPlayBackRateChange);
    player.addEventListener("enterpictureinpicture", this.onEnablePIP);
    player.addEventListener("leavepictureinpicture", this.onDisablePIP);
    player.addEventListener("webkitpresentationmodechanged", this.onPresentationModeChange);
    if (!this.shouldUseHLS(url)) {
      player.addEventListener("canplay", this.onReady);
    }
    if (playsinline) {
      player.setAttribute("playsinline", "");
      player.setAttribute("webkit-playsinline", "");
      player.setAttribute("x5-playsinline", "");
    }
  }
  removeListeners(player, url) {
    player.removeEventListener("canplay", this.onReady);
    player.removeEventListener("play", this.onPlay);
    player.removeEventListener("waiting", this.onBuffer);
    player.removeEventListener("playing", this.onBufferEnd);
    player.removeEventListener("pause", this.onPause);
    player.removeEventListener("seeked", this.onSeek);
    player.removeEventListener("ended", this.onEnded);
    player.removeEventListener("error", this.onError);
    player.removeEventListener("ratechange", this.onPlayBackRateChange);
    player.removeEventListener("enterpictureinpicture", this.onEnablePIP);
    player.removeEventListener("leavepictureinpicture", this.onDisablePIP);
    player.removeEventListener("webkitpresentationmodechanged", this.onPresentationModeChange);
    if (!this.shouldUseHLS(url)) {
      player.removeEventListener("canplay", this.onReady);
    }
  }
  shouldUseAudio(props) {
    if (props.config.forceVideo) {
      return false;
    }
    if (props.config.attributes.poster) {
      return false;
    }
    return import_patterns.AUDIO_EXTENSIONS.test(props.url) || props.config.forceAudio;
  }
  shouldUseHLS(url) {
    if (IS_SAFARI && this.props.config.forceSafariHLS || this.props.config.forceHLS) {
      return true;
    }
    if (IS_IOS || this.props.config.forceDisableHls) {
      return false;
    }
    return import_patterns.HLS_EXTENSIONS.test(url) || MATCH_CLOUDFLARE_STREAM.test(url);
  }
  shouldUseDASH(url) {
    return import_patterns.DASH_EXTENSIONS.test(url) || this.props.config.forceDASH;
  }
  shouldUseFLV(url) {
    return import_patterns.FLV_EXTENSIONS.test(url) || this.props.config.forceFLV;
  }
  load(url) {
    const { hlsVersion, hlsOptions, dashVersion, flvVersion } = this.props.config;
    if (this.hls) {
      this.hls.destroy();
    }
    if (this.dash) {
      this.dash.reset();
    }
    if (this.shouldUseHLS(url)) {
      (0, import_utils.getSDK)(HLS_SDK_URL.replace("VERSION", hlsVersion), HLS_GLOBAL).then((Hls) => {
        this.hls = new Hls(hlsOptions);
        this.hls.on(Hls.Events.MANIFEST_PARSED, () => {
          this.props.onReady();
        });
        this.hls.on(Hls.Events.ERROR, (e, data) => {
          this.props.onError(e, data, this.hls, Hls);
        });
        if (MATCH_CLOUDFLARE_STREAM.test(url)) {
          const id = url.match(MATCH_CLOUDFLARE_STREAM)[1];
          this.hls.loadSource(REPLACE_CLOUDFLARE_STREAM.replace("{id}", id));
        } else {
          this.hls.loadSource(url);
        }
        this.hls.attachMedia(this.player);
        this.props.onLoaded();
      });
    }
    if (this.shouldUseDASH(url)) {
      (0, import_utils.getSDK)(DASH_SDK_URL.replace("VERSION", dashVersion), DASH_GLOBAL).then((dashjs) => {
        this.dash = dashjs.MediaPlayer().create();
        this.dash.initialize(this.player, url, this.props.playing);
        this.dash.on("error", this.props.onError);
        if (parseInt(dashVersion) < 3) {
          this.dash.getDebug().setLogToBrowserConsole(false);
        } else {
          this.dash.updateSettings({ debug: { logLevel: dashjs.Debug.LOG_LEVEL_NONE } });
        }
        this.props.onLoaded();
      });
    }
    if (this.shouldUseFLV(url)) {
      (0, import_utils.getSDK)(FLV_SDK_URL.replace("VERSION", flvVersion), FLV_GLOBAL).then((flvjs) => {
        this.flv = flvjs.createPlayer({ type: "flv", url });
        this.flv.attachMediaElement(this.player);
        this.flv.on(flvjs.Events.ERROR, (e, data) => {
          this.props.onError(e, data, this.flv, flvjs);
        });
        this.flv.load();
        this.props.onLoaded();
      });
    }
    if (url instanceof Array) {
      this.player.load();
    } else if ((0, import_utils.isMediaStream)(url)) {
      try {
        this.player.srcObject = url;
      } catch (e) {
        this.player.src = window.URL.createObjectURL(url);
      }
    }
  }
  play() {
    const promise = this.player.play();
    if (promise) {
      promise.catch(this.props.onError);
    }
  }
  pause() {
    this.player.pause();
  }
  stop() {
    this.player.removeAttribute("src");
    if (this.dash) {
      this.dash.reset();
    }
  }
  seekTo(seconds, keepPlaying = true) {
    this.player.currentTime = seconds;
    if (!keepPlaying) {
      this.pause();
    }
  }
  setVolume(fraction) {
    this.player.volume = fraction;
  }
  enablePIP() {
    if (this.player.requestPictureInPicture && document.pictureInPictureElement !== this.player) {
      this.player.requestPictureInPicture();
    } else if ((0, import_utils.supportsWebKitPresentationMode)(this.player) && this.player.webkitPresentationMode !== "picture-in-picture") {
      this.player.webkitSetPresentationMode("picture-in-picture");
    }
  }
  disablePIP() {
    if (document.exitPictureInPicture && document.pictureInPictureElement === this.player) {
      document.exitPictureInPicture();
    } else if ((0, import_utils.supportsWebKitPresentationMode)(this.player) && this.player.webkitPresentationMode !== "inline") {
      this.player.webkitSetPresentationMode("inline");
    }
  }
  setPlaybackRate(rate) {
    try {
      this.player.playbackRate = rate;
    } catch (error) {
      this.props.onError(error);
    }
  }
  getDuration() {
    if (!this.player)
      return null;
    const { duration, seekable } = this.player;
    if (duration === Infinity && seekable.length > 0) {
      return seekable.end(seekable.length - 1);
    }
    return duration;
  }
  getCurrentTime() {
    if (!this.player)
      return null;
    return this.player.currentTime;
  }
  getSecondsLoaded() {
    if (!this.player)
      return null;
    const { buffered } = this.player;
    if (buffered.length === 0) {
      return 0;
    }
    const end = buffered.end(buffered.length - 1);
    const duration = this.getDuration();
    if (end > duration) {
      return duration;
    }
    return end;
  }
  getSource(url) {
    const useHLS = this.shouldUseHLS(url);
    const useDASH = this.shouldUseDASH(url);
    const useFLV = this.shouldUseFLV(url);
    if (url instanceof Array || (0, import_utils.isMediaStream)(url) || useHLS || useDASH || useFLV) {
      return void 0;
    }
    if (MATCH_DROPBOX_URL.test(url)) {
      return url.replace("www.dropbox.com", "dl.dropboxusercontent.com");
    }
    return url;
  }
  render() {
    const { url, playing, loop, controls, muted, config, width, height } = this.props;
    const useAudio = this.shouldUseAudio(this.props);
    const Element = useAudio ? "audio" : "video";
    const style = {
      width: width === "auto" ? width : "100%",
      height: height === "auto" ? height : "100%"
    };
    return /* @__PURE__ */ import_react.default.createElement(
      Element,
      {
        ref: this.ref,
        src: this.getSource(url),
        style,
        preload: "auto",
        autoPlay: playing || void 0,
        controls,
        muted,
        loop,
        ...config.attributes
      },
      url instanceof Array && url.map(this.renderSourceElement),
      config.tracks.map(this.renderTrack)
    );
  }
}
__publicField(FilePlayer, "displayName", "FilePlayer");
__publicField(FilePlayer, "canPlay", import_patterns.canPlay.file);


/***/ })

};
;