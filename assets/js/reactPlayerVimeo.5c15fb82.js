exports.id = 173;
exports.ids = [173];
exports.modules = {

/***/ 1423:
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
var Vimeo_exports = {};
__export(Vimeo_exports, {
  default: () => Vimeo
});
module.exports = __toCommonJS(Vimeo_exports);
var import_react = __toESM(__webpack_require__(6540));
var import_utils = __webpack_require__(5635);
var import_patterns = __webpack_require__(327);
const SDK_URL = "https://player.vimeo.com/api/player.js";
const SDK_GLOBAL = "Vimeo";
const cleanUrl = (url) => {
  return url.replace("/manage/videos", "");
};
class Vimeo extends import_react.Component {
  constructor() {
    super(...arguments);
    // Prevent checking isLoading when URL changes
    __publicField(this, "callPlayer", import_utils.callPlayer);
    __publicField(this, "duration", null);
    __publicField(this, "currentTime", null);
    __publicField(this, "secondsLoaded", null);
    __publicField(this, "mute", () => {
      this.setMuted(true);
    });
    __publicField(this, "unmute", () => {
      this.setMuted(false);
    });
    __publicField(this, "ref", (container) => {
      this.container = container;
    });
  }
  componentDidMount() {
    this.props.onMount && this.props.onMount(this);
  }
  load(url) {
    this.duration = null;
    (0, import_utils.getSDK)(SDK_URL, SDK_GLOBAL).then((Vimeo2) => {
      if (!this.container)
        return;
      const { playerOptions, title } = this.props.config;
      this.player = new Vimeo2.Player(this.container, {
        url: cleanUrl(url),
        autoplay: this.props.playing,
        muted: this.props.muted,
        loop: this.props.loop,
        playsinline: this.props.playsinline,
        controls: this.props.controls,
        ...playerOptions
      });
      this.player.ready().then(() => {
        const iframe = this.container.querySelector("iframe");
        iframe.style.width = "100%";
        iframe.style.height = "100%";
        if (title) {
          iframe.title = title;
        }
      }).catch(this.props.onError);
      this.player.on("loaded", () => {
        this.props.onReady();
        this.refreshDuration();
      });
      this.player.on("play", () => {
        this.props.onPlay();
        this.refreshDuration();
      });
      this.player.on("pause", this.props.onPause);
      this.player.on("seeked", (e) => this.props.onSeek(e.seconds));
      this.player.on("ended", this.props.onEnded);
      this.player.on("error", this.props.onError);
      this.player.on("timeupdate", ({ seconds }) => {
        this.currentTime = seconds;
      });
      this.player.on("progress", ({ seconds }) => {
        this.secondsLoaded = seconds;
      });
      this.player.on("bufferstart", this.props.onBuffer);
      this.player.on("bufferend", this.props.onBufferEnd);
      this.player.on("playbackratechange", (e) => this.props.onPlaybackRateChange(e.playbackRate));
    }, this.props.onError);
  }
  refreshDuration() {
    this.player.getDuration().then((duration) => {
      this.duration = duration;
    });
  }
  play() {
    const promise = this.callPlayer("play");
    if (promise) {
      promise.catch(this.props.onError);
    }
  }
  pause() {
    this.callPlayer("pause");
  }
  stop() {
    this.callPlayer("unload");
  }
  seekTo(seconds, keepPlaying = true) {
    this.callPlayer("setCurrentTime", seconds);
    if (!keepPlaying) {
      this.pause();
    }
  }
  setVolume(fraction) {
    this.callPlayer("setVolume", fraction);
  }
  setMuted(muted) {
    this.callPlayer("setMuted", muted);
  }
  setLoop(loop) {
    this.callPlayer("setLoop", loop);
  }
  setPlaybackRate(rate) {
    this.callPlayer("setPlaybackRate", rate);
  }
  getDuration() {
    return this.duration;
  }
  getCurrentTime() {
    return this.currentTime;
  }
  getSecondsLoaded() {
    return this.secondsLoaded;
  }
  render() {
    const { display } = this.props;
    const style = {
      width: "100%",
      height: "100%",
      overflow: "hidden",
      display
    };
    return /* @__PURE__ */ import_react.default.createElement(
      "div",
      {
        key: this.props.url,
        ref: this.ref,
        style
      }
    );
  }
}
__publicField(Vimeo, "displayName", "Vimeo");
__publicField(Vimeo, "canPlay", import_patterns.canPlay.vimeo);
__publicField(Vimeo, "forceLoad", true);


/***/ })

};
;