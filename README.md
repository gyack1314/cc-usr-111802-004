# 供水片区指标分析

项目保存供水片区的来源版次，按资料取得时间比较单期指标并给出区域规则判断。evidence 保存来源，metrics 计算同口径偏离，context 解释当前区域规则，report 保存报告。

规划扩展把储水异常、地面水源、跨区调水能力和用水优先级按明确期间联系：network 汇集覆盖规划期间的供给网络视图，allocation 比较每个片区在不同供给安排下的缺口与受影响人群（备用水源和调水线路按安排启用，避免仅凭异常地图限供有备用水源的片区），plan 形成并保留限水方案。卫星资料缺测、调水线路停用或水厂报表修订时，区分证据变化与实际保障能力变化，原方案保留，仅列出需重新审议的片区。样本是合成数据。

Python 3.11 以上，在项目根目录执行：

    python -m unittest discover -s tests -v
    python -m compileall -q climate_analysis tests
    python -m climate_analysis.cli inspect data/example.json
    python -m climate_analysis.cli plan data/planning_example.json

Dockerfile 可在 Linux 容器运行：docker build -t climate-analysis-004 .；docker run --rm climate-analysis-004。
