exports.id = 261;
exports.ids = [261];
exports.modules = {

/***/ 3911:
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
var Kaltura_exports = {};
__export(Kaltura_exports, {
  default: () => Kaltura
});
module.exports = __toCommonJS(Kaltura_exports);
var import_react = __toESM(__webpack_require__(7294));
var import_utils = __webpack_require__(8045);
var import_patterns = __webpack_require__(1776);
const SDK_URL = "https://cdn.embed.ly/player-0.1.0.min.js";
const SDK_GLOBAL = "playerjs";
class Kaltura extends import_react.Component {
  constructor() {
    super(...arguments);
    __publicField(this, "callPlayer", import_utils.callPlayer);
    __publicField(this, "duration", null);
    __publicField(this, "currentTime", null);
    __publicField(this, "secondsLoaded", null);
    __publicField(this, "mute", () => {
      this.callPlayer("mute");
    });
    __publicField(this, "unmute", () => {
      this.callPlayer("unmute");
    });
    __publicField(this, "ref", (iframe) => {
      this.iframe = iframe;
    });
  }
  componentDidMount() {
    this.props.onMount && this.props.onMount(this);
  }
  load(url) {
    (0, import_utils.getSDK)(SDK_URL, SDK_GLOBAL).then((playerjs) => {
      if (!this.iframe)
        return;
      this.player = new playerjs.Player(this.iframe);
      this.player.on("ready", () => {
        setTimeout(() => {
          this.player.isReady = true;
          this.player.setLoop(this.props.loop);
          if (this.props.muted) {
            this.player.mute();
          }
          this.addListeners(this.player, this.props);
          this.props.onReady();
        }, 500);
      });
    }, this.props.onError);
  }
  addListeners(player, props) {
    player.on("play", props.onPlay);
    player.on("pause", props.onPause);
    player.on("ended", props.onEnded);
    player.on("error", props.onError);
    player.on("timeupdate", ({ duration, seconds }) => {
      this.duration = duration;
      this.currentTime = seconds;
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
    this.callPlayer("setCurrentTime", seconds);
    if (!keepPlaying) {
      this.pause();
    }
  }
  setVolume(fraction) {
    this.callPlayer("setVolume", fraction);
  }
  setLoop(loop) {
    this.callPlayer("setLoop", loop);
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
    const style = {
      width: "100%",
      height: "100%"
    };
    return /* @__PURE__ */ import_react.default.createElement(
      "iframe",
      {
        ref: this.ref,
        src: this.props.url,
        frameBorder: "0",
        scrolling: "no",
        style,
        allow: "encrypted-media; autoplay; fullscreen;",
        referrerPolicy: "no-referrer-when-downgrade"
      }
    );
  }
}
__publicField(Kaltura, "displayName", "Kaltura");
__publicField(Kaltura, "canPlay", import_patterns.canPlay.kaltura);


/***/ })

};
;