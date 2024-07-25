exports.id = 353;
exports.ids = [353];
exports.modules = {

/***/ 6734:
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
var Preview_exports = {};
__export(Preview_exports, {
  default: () => Preview
});
module.exports = __toCommonJS(Preview_exports);
var import_react = __toESM(__webpack_require__(6540));
const ICON_SIZE = "64px";
const cache = {};
class Preview extends import_react.Component {
  constructor() {
    super(...arguments);
    __publicField(this, "mounted", false);
    __publicField(this, "state", {
      image: null
    });
    __publicField(this, "handleKeyPress", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        this.props.onClick();
      }
    });
  }
  componentDidMount() {
    this.mounted = true;
    this.fetchImage(this.props);
  }
  componentDidUpdate(prevProps) {
    const { url, light } = this.props;
    if (prevProps.url !== url || prevProps.light !== light) {
      this.fetchImage(this.props);
    }
  }
  componentWillUnmount() {
    this.mounted = false;
  }
  fetchImage({ url, light, oEmbedUrl }) {
    if (import_react.default.isValidElement(light)) {
      return;
    }
    if (typeof light === "string") {
      this.setState({ image: light });
      return;
    }
    if (cache[url]) {
      this.setState({ image: cache[url] });
      return;
    }
    this.setState({ image: null });
    return window.fetch(oEmbedUrl.replace("{url}", url)).then((response) => response.json()).then((data) => {
      if (data.thumbnail_url && this.mounted) {
        const image = data.thumbnail_url.replace("height=100", "height=480").replace("-d_295x166", "-d_640");
        this.setState({ image });
        cache[url] = image;
      }
    });
  }
  render() {
    const { light, onClick, playIcon, previewTabIndex, previewAriaLabel } = this.props;
    const { image } = this.state;
    const isElement = import_react.default.isValidElement(light);
    const flexCenter = {
      display: "flex",
      alignItems: "center",
      justifyContent: "center"
    };
    const styles = {
      preview: {
        width: "100%",
        height: "100%",
        backgroundImage: image && !isElement ? `url(${image})` : void 0,
        backgroundSize: "cover",
        backgroundPosition: "center",
        cursor: "pointer",
        ...flexCenter
      },
      shadow: {
        background: "radial-gradient(rgb(0, 0, 0, 0.3), rgba(0, 0, 0, 0) 60%)",
        borderRadius: ICON_SIZE,
        width: ICON_SIZE,
        height: ICON_SIZE,
        position: isElement ? "absolute" : void 0,
        ...flexCenter
      },
      playIcon: {
        borderStyle: "solid",
        borderWidth: "16px 0 16px 26px",
        borderColor: "transparent transparent transparent white",
        marginLeft: "7px"
      }
    };
    const defaultPlayIcon = /* @__PURE__ */ import_react.default.createElement("div", { style: styles.shadow, className: "react-player__shadow" }, /* @__PURE__ */ import_react.default.createElement("div", { style: styles.playIcon, className: "react-player__play-icon" }));
    return /* @__PURE__ */ import_react.default.createElement(
      "div",
      {
        style: styles.preview,
        className: "react-player__preview",
        onClick,
        tabIndex: previewTabIndex,
        onKeyPress: this.handleKeyPress,
        ...previewAriaLabel ? { "aria-label": previewAriaLabel } : {}
      },
      isElement ? light : null,
      playIcon || defaultPlayIcon
    );
  }
}


/***/ })

};
;