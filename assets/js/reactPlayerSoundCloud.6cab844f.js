exports.id = 125;
exports.ids = [125];
exports.modules = {

/***/ 2648:
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
var SoundCloud_exports = {};
__export(SoundCloud_exports, {
  default: () => SoundCloud
});
module.exports = __toCommonJS(SoundCloud_exports);
var import_react = __toESM(__webpack_require__(7294));
var import_utils = __webpack_require__(8045);
var import_patterns = __webpack_require__(1776);
const SDK_URL = "https://w.soundcloud.com/player/api.js";
const SDK_GLOBAL = "SC";
class SoundCloud extends import_react.Component {
  constructor() {
    super(...arguments);
    __publicField(this, "callPlayer", import_utils.callPlayer);
    __publicField(this, "duration", null);
    __publicField(this, "currentTime", null);
    __publicField(this, "fractionLoaded", null);
    __publicField(this, "mute", () => {
      this.setVolume(0);
    });
    __publicField(this, "unmute", () => {
      if (this.props.volume !== null) {
        this.setVolume(this.props.volume);
      }
    });
    __publicField(this, "ref", (iframe) => {
      this.iframe = iframe;
    });
  }
  componentDidMount() {
    this.props.onMount && this.props.onMount(this);
  }
  load(url, isReady) {
    (0, import_utils.getSDK)(SDK_URL, SDK_GLOBAL).then((SC) => {
      if (!this.iframe)
        return;
      const { PLAY, PLAY_PROGRESS, PAUSE, FINISH, ERROR } = SC.Widget.Events;
      if (!isReady) {
        this.player = SC.Widget(this.iframe);
        this.player.bind(PLAY, this.props.onPlay);
        this.player.bind(PAUSE, () => {
          const remaining = this.duration - this.currentTime;
          if (remaining < 0.05) {
            return;
          }
          this.props.onPause();
        });
        this.player.bind(PLAY_PROGRESS, (e) => {
          this.currentTime = e.currentPosition / 1e3;
          this.fractionLoaded = e.loadedProgress;
        });
        this.player.bind(FINISH, () => this.props.onEnded());
        this.player.bind(ERROR, (e) => this.props.onError(e));
      }
      this.player.load(url, {
        ...this.props.config.options,
        callback: () => {
          this.player.getDuration((duration) => {
            this.duration = duration / 1e3;
            this.props.onReady();
          });
        }
      });
    });
  }
  play() {
    this.callPlayer("play");
  }
  pause() {
    this.callPlayer("pause");
  }
  stop() {
  }
  seekTo(seconds, keepPlaying = true) {
    this.callPlayer("seekTo", seconds * 1e3);
    if (!keepPlaying) {
      this.pause();
    }
  }
  setVolume(fraction) {
    this.callPlayer("setVolume", fraction * 100);
  }
  getDuration() {
    return this.duration;
  }
  getCurrentTime() {
    return this.currentTime;
  }
  getSecondsLoaded() {
    return this.fractionLoaded * this.duration;
  }
  render() {
    const { display } = this.props;
    const style = {
      width: "100%",
      height: "100%",
      display
    };
    return /* @__PURE__ */ import_react.default.createElement(
      "iframe",
      {
        ref: this.ref,
        src: `https://w.soundcloud.com/player/?url=${encodeURIComponent(this.props.url)}`,
        style,
        frameBorder: 0,
        allow: "autoplay"
      }
    );
  }
}
__publicField(SoundCloud, "displayName", "SoundCloud");
__publicField(SoundCloud, "canPlay", import_patterns.canPlay.soundcloud);
__publicField(SoundCloud, "loopOnEnded", true);


/***/ })

};
;