import re

from penai.svg import ensure_unique_ids_in_svg_code

generated_svg_code = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:penpot="https://penpot.app/xmlns" viewBox="1136.0 474.0 72.0 72.0" version="1.1" style="width:100%;height:100%;background:#E8E9EA" fill="none" preserveAspectRatio="xMinYMin meet">
  <defs>
    <mask id="mask5">
      <rect x="1136" y="474" width="72" height="72" fill="white"/>
      <rect x="1168.4" y="495.6" width="7.2" height="28.8" fill="black"/>
      <rect x="1157.6" y="510" width="7.2" height="14.4" fill="black"/>
      <rect x="1179.2" y="504.6" width="7.2" height="19.8" fill="black"/>
    </mask>
  </defs>
  <circle cx="1172" cy="510" r="30" fill="#800080" mask="url(#mask5)"/>
</svg>"""


def test_post_process_svg() -> None:
    processed_svg_code = ensure_unique_ids_in_svg_code(generated_svg_code)
    all_ids = re.findall(r'id="(.*?)"', processed_svg_code)
    assert len(all_ids) == len(set(all_ids))
    assert "mask5" not in all_ids
