exports.id = 723;
exports.ids = [723];
exports.modules = {

/***/ 7553:
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
var Mux_exports = {};
__export(Mux_exports, {
  default: () => Mux
});
module.exports = __toCommonJS(Mux_exports);
var import_react = __toESM(__webpack_require__(6540));
var import_patterns = __webpack_require__(327);
const SDK_URL = "https://cdn.jsdelivr.net/npm/@mux/mux-player@VERSION/dist/mux-player.mjs";
class Mux extends import_react.Component {
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
    __publicField(this, "onSeek", (e) => {
      this.props.onSeek(e.target.currentTime);
    });
    __publicField(this, "onDurationChange", () => {
      const duration = this.getDuration();
      this.props.onDuration(duration);
    });
    __publicField(this, "mute", () => {
      this.player.muted = true;
    });
    __publicField(this, "unmute", () => {
      this.player.muted = false;
    });
    __publicField(this, "ref", (player) => {
      this.player = player;
    });
  }
  componentDidMount() {
    this.props.onMount && this.props.onMount(this);
    this.addListeners(this.player);
    const playbackId = this.getPlaybackId(this.props.url);
    if (playbackId) {
      this.player.playbackId = playbackId;
    }
  }
  componentWillUnmount() {
    this.player.playbackId = null;
    this.removeListeners(this.player);
  }
  addListeners(player) {
    const { playsinline } = this.props;
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
    player.addEventListener("canplay", this.onReady);
    if (playsinline) {
      player.setAttribute("playsinline", "");
    }
  }
  removeListeners(player) {
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
    player.removeEventListener("canplay", this.onReady);
  }
  async load(url) {
    var _a;
    const { onError, config } = this.props;
    if (!((_a = globalThis.customElements) == null ? void 0 : _a.get("mux-player"))) {
      try {
        const sdkUrl = SDK_URL.replace("VERSION", config.version);
        await import(
          /* webpackIgnore: true */
          `${sdkUrl}`
        );
        this.props.onLoaded();
      } catch (error) {
        onError(error);
      }
    }
    const [, id] = url.match(import_patterns.MATCH_URL_MUX);
    this.player.playbackId = id;
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
    this.player.playbackId = null;
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
    }
  }
  disablePIP() {
    if (document.exitPictureInPicture && document.pictureInPictureElement === this.player) {
      document.exitPictureInPicture();
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
  getPlaybackId(url) {
    const [, id] = url.match(import_patterns.MATCH_URL_MUX);
    return id;
  }
  render() {
    const { url, playing, loop, controls, muted, config, width, height } = this.props;
    const style = {
      width: width === "auto" ? width : "100%",
      height: height === "auto" ? height : "100%"
    };
    if (controls === false) {
      style["--controls"] = "none";
    }
    return /* @__PURE__ */ import_react.default.createElement(
      "mux-player",
      {
        ref: this.ref,
        "playback-id": this.getPlaybackId(url),
        style,
        preload: "auto",
        autoPlay: playing || void 0,
        muted: muted ? "" : void 0,
        loop: loop ? "" : void 0,
        ...config.attributes
      }
    );
  }
}
__publicField(Mux, "displayName", "Mux");
__publicField(Mux, "canPlay", import_patterns.canPlay.mux);


/***/ })

};
;