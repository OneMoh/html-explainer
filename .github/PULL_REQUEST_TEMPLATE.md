## 这次改了什么

<!-- 一两句话。原来错在哪，这个改动做了什么？ -->

## 为什么要改

<!--
如果这修的是一个静默失败，请说明它原来表现成什么样、你又是怎么证明病因的。
「我试了 X，还是坏的；改了 Y，就好了」在这里是真正有用的信息 ——
这条流水线的输出经常看着挺像样，其实是错的。
-->

## 怎么验证的

<!--
不要写「应该能跑」。你实际跑了什么？
例如 `node scripts/peek_frame.mjs . hook --at 25,50,85`，并检查了 50% 那一帧
-->

## 检查清单

- [ ] `python scripts/lint_frames.py --project <project>` 对我动过的帧没有 FAIL
- [ ] 我真的渲染过这次改动，并看过输出
- [ ] 没有引入外部字体、CDN 链接或硬编码颜色字面量
- [ ] 新增的踩坑记录（如果有）已按下一个编号追加到 `references/lessons.md`
- [ ] `python scripts/check_integrity.py` 通过
- [ ] 涉及使用者可见行为的改动，`README.md` 与 `README.en.md` 已同步更新
- [ ] 如果新增或再衍生了第三方内容，`THIRD_PARTY_NOTICES.md` 已更新

## 相关 issue

<!-- Closes #... -->
