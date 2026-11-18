# 供水片区数据约定

observation、reference、rule 三种记录分别表示观测、参照和区域规则。metric、region、unit 共同表示现有单期可比口径，来源版次与取得时间独立保留。

## 规划期间记录

anomaly、plant、transfer、priority 四种记录的 payload 都带明确 period（start、end），只有完整覆盖规划期间的版本进入供给网络视图，其余列入排除清单：

- anomaly：卫星陆地水储量异常，payload 含 region、value、unit；value 为 null 表示该期卫星资料缺测。
- plant：水厂可供水量，payload 含 region、capacity、unit、role（常规/备用）。
- transfer：跨区调水线路，payload 含 from、to、capacity、unit、status（启用/停用）。
- priority：用水优先级，payload 含 region、unit、tiers；tier 的 level 越小优先级越高，demand 与 population 表示该级需水与削减时受影响人口。

## 变化分类

报表类记录（anomaly、plant、priority）的修订只改变掌握的资料，归为证据变化；transfer 的状态或能力修订改变实际保障能力，归为能力变化。两类变化都不改动已保留的限水方案，只把受影响片区列入重新审议清单，并附重算缺口供审议参考。
