const SvgSpecStream = ({ isDark: _isDark, ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="236 286 800 580"
    fill="currentColor"
    {...props}
  >
    <defs>
      <mask
        id="specstream-mark-cutout"
        maskUnits="userSpaceOnUse"
        x={236}
        y={286}
        width={800}
        height={580}
      >
        <rect x={236} y={286} width={800} height={580} fill="#fff" />
        <g
          fill="#000"
          transform="translate(874 722) scale(1.6) translate(-874 -722)"
        >
          <path d="M848 722C849 712 852 704 849 696C846 690 843 684 842 676C837 670 836 660 838 652L836 641L846 649C852 647 858 647 862 649L870 640L871 655C873 663 872 668 868 672C884 678 897 692 900 722Z" />
          <path d="M852 719L900 720L1004 735L950 792Z" />
        </g>
      </mask>
    </defs>
    <path
      mask="url(#specstream-mark-cutout)"
      d="M470 298C420 300 330 312 290 334C265 348 272 368 305 382C360 405 440 432 455 472C468 510 420 545 350 590C285 632 248 668 250 712C253 790 390 850 610 851C820 852 960 810 1000 740C1022 700 1018 672 996 640C950 585 850 530 700 480C560 440 420 408 345 380C318 370 312 356 330 346C370 325 430 306 470 298Z"
    />
  </svg>
);

export default SvgSpecStream;
