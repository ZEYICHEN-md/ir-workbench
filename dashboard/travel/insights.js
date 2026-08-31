// ============================================================
// 旅游看板洞察投影 — 请勿手改
// 权威：data/canonical/travel-insights.json
// 重新生成：ir industry generate-dashboard
// ============================================================

const INSIGHTS = {
  "meta": {
    "basedOnTravelJsonUpdatedAt": "2026-08-15",
    "confirmedAt": {
      "weekly": "2026-08-31",
      "monthly": "2026-08-31",
      "quarterly": "2026-08-31"
    },
    "stale": {
      "weekly": false,
      "monthly": false,
      "quarterly": false
    }
  },
  "weekly": {
    "zh": [
      {
        "tag": "highlight",
        "title": "客运量连续五周转正，票价降幅收窄",
        "body": "8/9-8/15 国内航空客运量同比 <span class=\"num-highlight\">+4.0%</span>，为连续第五周转正；机票票价同比 <span class=\"num-highlight\">-6.0%</span>，较前一周 -8.0% 收窄 2 个百分点，客运航班量 <span class=\"num-highlight\">+2.0%</span>。航旅纵横《2026 年暑运出行总结报告》称今年暑运启动偏晚，亲子游、避暑游需求集中在 8 月中上旬释放、出行高峰后移，与这一周量稳价升相符。若高峰确实后移，8 月下旬的回落会比往年更陡。",
        "refs": [
          "weekly.aviationPax@8/9-8/15",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.aviationTicket@8/9-8/15",
          "weekly.aviationFlight@8/9-8/15"
        ]
      },
      {
        "tag": "risk",
        "title": "酒店 RevPAR 降幅走阔至 -4.1%",
        "body": "8/9-8/15 酒店 RevPAR 同比 <span class=\"num-highlight\">-4.1%</span>，较前一周 -1.5% 明显走阔，入住率 <span class=\"num-highlight\">-3.4%</span>、ADR <span class=\"num-highlight\">-0.7%</span> 同步转弱。同一周航空客流仍在增长，住宿端量价齐跌，暑运客流没有传导到酒店收益。后续看开学季前后 RevPAR 能否止住走阔。",
        "refs": [
          "weekly.hotelRevPAR@7/26-8/1",
          "weekly.hotelRevPAR@8/2-8/8",
          "weekly.hotelRevPAR@8/9-8/15",
          "weekly.hotelOccupancy@8/9-8/15",
          "weekly.hotelADR@8/9-8/15",
          "weekly.aviationPax@8/9-8/15"
        ]
      },
      {
        "tag": "risk",
        "title": "票价同比连续八周为负",
        "body": "自 6/21-6/27 起机票票价同比连续八周为负，8/9-8/15 仍为 <span class=\"num-highlight\">-6.0%</span>，区间内在 -6% 到 -9% 之间反复。暑运旺季都没能回正，运力供给充裕、旅客价格敏感的格局没有变化。这次收窄能否延续到 9 月淡季是关键。",
        "refs": [
          "weekly.aviationTicket@6/21-6/27",
          "weekly.aviationTicket@7/26-8/1",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.aviationTicket@8/9-8/15"
        ]
      },
      {
        "tag": "outlook",
        "title": "开学后量与价会不会各走一边",
        "body": "待验证三件事：客运量在暑运收官后能否守住正增长、票价收窄是趋势还是单周反弹、酒店 RevPAR 能否止住走阔。若客流回落而票价不回，暑运尾段的收益改善空间会被进一步压缩。",
        "refs": [
          "weekly.aviationPax@8/9-8/15",
          "weekly.aviationTicket@8/9-8/15",
          "weekly.hotelRevPAR@8/9-8/15"
        ]
      }
    ],
    "en": [
      {
        "tag": "highlight",
        "title": "Air passenger volume positive for a fifth week, fare decline narrows",
        "body": "Domestic air passenger volume rose <span class=\"num-highlight\">+4.0%</span> YoY in 8/9-8/15, a fifth consecutive week of growth; average fares came in at <span class=\"num-highlight\">-6.0%</span> YoY, narrowing 2pp from -8.0% the previous week, with passenger flights at <span class=\"num-highlight\">+2.0%</span>. Umetrip's 2026 summer travel review notes the season started late, with family and cool-weather trips concentrated in the first half of August and the peak shifting later, consistent with this week's steady volume and firmer pricing. If the peak has indeed shifted, the late-August drop-off will be steeper than usual.",
        "refs": [
          "weekly.aviationPax@8/9-8/15",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.aviationTicket@8/9-8/15",
          "weekly.aviationFlight@8/9-8/15"
        ]
      },
      {
        "tag": "risk",
        "title": "Hotel RevPAR decline widens to -4.1%",
        "body": "Hotel RevPAR was <span class=\"num-highlight\">-4.1%</span> YoY in 8/9-8/15, widening sharply from -1.5% the previous week, with occupancy at <span class=\"num-highlight\">-3.4%</span> and ADR at <span class=\"num-highlight\">-0.7%</span>. Air traffic kept growing in the same week while lodging softened on both volume and rate, so summer travel did not pass through to hotel revenue. Watch whether RevPAR stops widening around the back-to-school period.",
        "refs": [
          "weekly.hotelRevPAR@7/26-8/1",
          "weekly.hotelRevPAR@8/2-8/8",
          "weekly.hotelRevPAR@8/9-8/15",
          "weekly.hotelOccupancy@8/9-8/15",
          "weekly.hotelADR@8/9-8/15",
          "weekly.aviationPax@8/9-8/15"
        ]
      },
      {
        "tag": "risk",
        "title": "Air fares negative for eight consecutive weeks",
        "body": "Air fares have been negative YoY for eight consecutive weeks since 6/21-6/27, at <span class=\"num-highlight\">-6.0%</span> in 8/9-8/15 and ranging between -6% and -9% over that span. Even peak summer failed to turn them positive; ample capacity and price-sensitive travellers remain the backdrop. Whether this narrowing carries into the September low season is the key question.",
        "refs": [
          "weekly.aviationTicket@6/21-6/27",
          "weekly.aviationTicket@7/26-8/1",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.aviationTicket@8/9-8/15"
        ]
      },
      {
        "tag": "outlook",
        "title": "Will volume and price diverge after schools reopen",
        "body": "Three things to watch: whether air passenger volume holds positive growth after the summer season closes, whether the fare narrowing is a trend or a one-week rebound, and whether hotel RevPAR stops widening. If traffic falls back while fares stay weak, the room for yield improvement in the closing weeks of summer narrows further.",
        "refs": [
          "weekly.aviationPax@8/9-8/15",
          "weekly.aviationTicket@8/9-8/15",
          "weekly.hotelRevPAR@8/9-8/15"
        ]
      }
    ]
  },
  "monthly": {
    "zh": [
      {
        "tag": "highlight",
        "title": "7 月国内航空转正，摆动逾 11 个百分点",
        "body": "7 月国内航空客运量同比民航局口径 <span class=\"num-highlight\">+4.1%</span>、三大航 <span class=\"num-highlight\">+5.3%</span>，6 月分别为 -7.1% 和 -7.8%，一个月内摆动 11.1 与 13.2 个百分点。暑运客流集中释放，航旅纵横统计 7/1–8/25 国内航线旅客量同比增长超 4%，方向与月度口径一致。8 月月度能否接住这个转正是下一个观察点。",
        "refs": [
          "monthly.domAviationCAAC@7月",
          "monthly.domAviationBig3@7月",
          "monthly.domAviationCAAC@6月",
          "monthly.domAviationBig3@6月"
        ]
      },
      {
        "tag": "highlight",
        "title": "国际运力缺口收窄至 -11.9%",
        "body": "7 月国际航班运力（对比 2019 年）<span class=\"num-highlight\">-11.9%</span>，较 6 月 -16.3% 收窄 4.4 个百分点；国际客运量民航局口径 <span class=\"num-highlight\">+2.5%</span>、三大航 <span class=\"num-highlight\">+6.0%</span>，6 月分别为 -2.0% 和 -0.2%，双双由负转正。暑期出入境需求回暖，航旅纵横统计暑运出入境旅客量同比增长约 3%。后续看冬春航季换季能否延续加班节奏。",
        "refs": [
          "monthly.intlCapacity@7月",
          "monthly.intlCapacity@6月",
          "monthly.intlAviationCAAC@7月",
          "monthly.intlAviationCAAC@6月",
          "monthly.intlAviationBig3@7月",
          "monthly.intlAviationBig3@6月"
        ]
      },
      {
        "tag": "risk",
        "title": "7 月酒店量价齐跌，RevPAR -4.0%",
        "body": "7 月酒店 RevPAR 同比 <span class=\"num-highlight\">-4.0%</span>，入住率 <span class=\"num-highlight\">-3.0%</span>、ADR <span class=\"num-highlight\">-1.0%</span>；6 月这三项是 -0.4%、-2.5%、+2.2%，ADR 由正转负是主要变化。国内航空在同一个月转正，暑运客流没有变成住宿收益。8 月旺季尾段能否收窄是关键。",
        "refs": [
          "monthly.hotelRevPAR@7月",
          "monthly.hotelOccupancy@7月",
          "monthly.hotelADR@7月",
          "monthly.hotelRevPAR@6月",
          "monthly.hotelADR@6月"
        ]
      },
      {
        "tag": "risk",
        "title": "铁路 7 月转负 -2.6%",
        "body": "7 月铁路客运量同比 <span class=\"num-highlight\">-2.6%</span>，结束 2–6 月连续五个月正增长（6 月 +0.4%、5 月 +1.9%）。同月国内航空转正 +4.1%，两种运输方式今年首次明显反向。后续看 8 月是不是单月扰动。",
        "refs": [
          "monthly.railway@7月",
          "monthly.railway@6月",
          "monthly.railway@5月",
          "monthly.domAviationCAAC@7月"
        ]
      },
      {
        "tag": "outlook",
        "title": "8 月月度能否接住 7 月的转正",
        "body": "关键看国内航空的正增长是暑运单月效应还是趋势起点、酒店 RevPAR 降幅能否收窄、铁路会不会连续两个月为负。8 月是暑运收官月，去年同期基数与今年高峰后移叠加，读数会比 7 月更难解释。",
        "refs": [
          "monthly.domAviationCAAC@7月",
          "monthly.hotelRevPAR@7月",
          "monthly.railway@7月"
        ]
      }
    ],
    "en": [
      {
        "tag": "highlight",
        "title": "Domestic aviation turns positive in July, an 11pp swing",
        "body": "July domestic air passenger volume was <span class=\"num-highlight\">+4.1%</span> YoY on the CAAC measure and <span class=\"num-highlight\">+5.3%</span> for the Big 3, against -7.1% and -7.8% in June, swings of 11.1pp and 13.2pp in a single month. Summer traffic was released in a concentrated burst, and Umetrip counted domestic route passengers up more than 4% YoY between 1 July and 25 August, pointing the same way as the monthly series. Whether August holds this reversal is the next checkpoint.",
        "refs": [
          "monthly.domAviationCAAC@7月",
          "monthly.domAviationBig3@7月",
          "monthly.domAviationCAAC@6月",
          "monthly.domAviationBig3@6月"
        ]
      },
      {
        "tag": "highlight",
        "title": "International capacity gap narrows to -11.9%",
        "body": "July international flight capacity was <span class=\"num-highlight\">-11.9%</span> versus 2019, narrowing 4.4pp from -16.3% in June; international passenger volume was <span class=\"num-highlight\">+2.5%</span> on the CAAC measure and <span class=\"num-highlight\">+6.0%</span> for the Big 3, against -2.0% and -0.2% in June, both turning positive. Outbound and inbound demand recovered over the summer, with Umetrip counting cross-border passengers up about 3% YoY. Watch whether the winter-spring schedule change sustains the added flights.",
        "refs": [
          "monthly.intlCapacity@7月",
          "monthly.intlCapacity@6月",
          "monthly.intlAviationCAAC@7月",
          "monthly.intlAviationCAAC@6月",
          "monthly.intlAviationBig3@7月",
          "monthly.intlAviationBig3@6月"
        ]
      },
      {
        "tag": "risk",
        "title": "July hotels weak on both volume and rate, RevPAR -4.0%",
        "body": "July hotel RevPAR was <span class=\"num-highlight\">-4.0%</span> YoY, with occupancy at <span class=\"num-highlight\">-3.0%</span> and ADR at <span class=\"num-highlight\">-1.0%</span>; the same three read -0.4%, -2.5% and +2.2% in June, with ADR flipping negative the main change. Domestic aviation turned positive in the same month, so summer traffic did not convert into lodging revenue. Whether the decline narrows in the closing weeks of the peak season is the key question.",
        "refs": [
          "monthly.hotelRevPAR@7月",
          "monthly.hotelOccupancy@7月",
          "monthly.hotelADR@7月",
          "monthly.hotelRevPAR@6月",
          "monthly.hotelADR@6月"
        ]
      },
      {
        "tag": "risk",
        "title": "Railway turns negative in July at -2.6%",
        "body": "July railway passenger volume was <span class=\"num-highlight\">-2.6%</span> YoY, ending five consecutive months of growth from February to June (+0.4% in June, +1.9% in May). Domestic aviation turned positive at +4.1% in the same month, the first clear divergence between the two modes this year. Watch whether August shows this was a one-month disturbance.",
        "refs": [
          "monthly.railway@7月",
          "monthly.railway@6月",
          "monthly.railway@5月",
          "monthly.domAviationCAAC@7月"
        ]
      },
      {
        "tag": "outlook",
        "title": "Can August hold July's reversal",
        "body": "The questions are whether the positive growth in domestic aviation is a one-month summer effect or the start of a trend, whether hotel RevPAR narrows its decline, and whether railway posts a second negative month. August closes the summer season, and last year's base combined with this year's later peak will make the reading harder to interpret than July's.",
        "refs": [
          "monthly.domAviationCAAC@7月",
          "monthly.hotelRevPAR@7月",
          "monthly.railway@7月"
        ]
      }
    ]
  },
  "quarterly": {
    "zh": [
      {
        "tag": "highlight",
        "title": "Q2 酒店 RevPAR 仍为正 +2.0%",
        "body": "Q2 酒店 RevPAR 同比 <span class=\"num-highlight\">+2.0%</span>，ADR <span class=\"num-highlight\">+2.9%</span>、入住率 <span class=\"num-highlight\">-0.8%</span>，较 Q1 的 +4.8% 放缓但未转负。增长完全由房价贡献，量已经在收缩。Q3 若 ADR 跟着松动，RevPAR 转负的风险不小。",
        "refs": [
          "quarterly.q2.hotelRevPAR",
          "quarterly.q2.hotelADR",
          "quarterly.q2.hotelOccupancy",
          "quarterly.q1.hotelRevPAR"
        ]
      },
      {
        "tag": "highlight",
        "title": "铁路两季稳增，Q2 +4.6%",
        "body": "Q2 铁路客运量同比 <span class=\"num-highlight\">+4.6%</span>，Q1 <span class=\"num-highlight\">+5.7%</span>，是上半年唯一两个季度都稳在 4% 以上的指标。航空在这两季大幅摆动，铁路撑住了国内出行的基本盘。Q3 能否延续要看暑运收官后的通道客流。",
        "refs": [
          "quarterly.q2.railway",
          "quarterly.q1.railway",
          "quarterly.q2.domAviationCAAC"
        ]
      },
      {
        "tag": "risk",
        "title": "Q2 国内航空转负，摆动逾 10 个百分点",
        "body": "Q2 国内航空客运量同比民航局口径 <span class=\"num-highlight\">-5.2%</span>、三大航 <span class=\"num-highlight\">-6.0%</span>，Q1 分别为 +5.5% 和 +5.5%，摆动 10.7 与 11.5 个百分点。二季度传统淡季叠加航司主动收运力。Q3 能否回正，是全年国内航空读数的分水岭。",
        "refs": [
          "quarterly.q2.domAviationCAAC",
          "quarterly.q2.domAviationBig3",
          "quarterly.q1.domAviationCAAC",
          "quarterly.q1.domAviationBig3"
        ]
      },
      {
        "tag": "risk",
        "title": "Q2 国际运力缺口扩大至 -14.0%",
        "body": "Q2 国际航班运力（对比 2019 年）<span class=\"num-highlight\">-14.0%</span>，Q1 -9.6%，缺口反向走阔 4.4 个百分点；国际客运量增速同步从 Q1 +10.3% 降到 <span class=\"num-highlight\">+2.7%</span>，三大航从 +12.8% 降到 +1.2%。运力恢复没有跟上一季度的势头。Q3 的增班节奏决定缺口会不会继续走阔。",
        "refs": [
          "quarterly.q2.intlCapacity",
          "quarterly.q1.intlCapacity",
          "quarterly.q2.intlAviationCAAC",
          "quarterly.q1.intlAviationCAAC",
          "quarterly.q2.intlAviationBig3",
          "quarterly.q1.intlAviationBig3"
        ]
      },
      {
        "tag": "outlook",
        "title": "Q3 国内航空能否回正",
        "body": "三季度覆盖整个暑运，是全年国内出行最集中的一段。关键看国内航空能否摆脱二季度的负增长、酒店 RevPAR 在入住率下滑时能否守住正增长、国际运力缺口会不会继续走阔。旺季弹性能否抵掉二季度的拖累，是全年读数的主要变量。",
        "refs": [
          "quarterly.q2.domAviationCAAC",
          "quarterly.q2.hotelRevPAR",
          "quarterly.q2.intlCapacity"
        ]
      }
    ],
    "en": [
      {
        "tag": "highlight",
        "title": "Q2 hotel RevPAR still positive at +2.0%",
        "body": "Q2 hotel RevPAR was <span class=\"num-highlight\">+2.0%</span> YoY, with ADR at <span class=\"num-highlight\">+2.9%</span> and occupancy at <span class=\"num-highlight\">-0.8%</span>, slowing from +4.8% in Q1 but not turning negative. All of the growth came from rate while volume was already contracting. If ADR softens in Q3, the risk of RevPAR turning negative is material.",
        "refs": [
          "quarterly.q2.hotelRevPAR",
          "quarterly.q2.hotelADR",
          "quarterly.q2.hotelOccupancy",
          "quarterly.q1.hotelRevPAR"
        ]
      },
      {
        "tag": "highlight",
        "title": "Railway steady across both quarters, Q2 +4.6%",
        "body": "Q2 railway passenger volume was <span class=\"num-highlight\">+4.6%</span> YoY after <span class=\"num-highlight\">+5.7%</span> in Q1, the only indicator holding above 4% in both quarters of the first half. Aviation swung sharply across those two quarters while railway held the floor for domestic travel. Whether Q3 sustains it depends on trunk-route traffic after the summer season.",
        "refs": [
          "quarterly.q2.railway",
          "quarterly.q1.railway",
          "quarterly.q2.domAviationCAAC"
        ]
      },
      {
        "tag": "risk",
        "title": "Q2 domestic aviation turns negative, a swing above 10pp",
        "body": "Q2 domestic air passenger volume was <span class=\"num-highlight\">-5.2%</span> YoY on the CAAC measure and <span class=\"num-highlight\">-6.0%</span> for the Big 3, against +5.5% and +5.5% in Q1, swings of 10.7pp and 11.5pp. The traditional second-quarter lull combined with airlines cutting capacity. Whether Q3 returns to growth is the dividing line for the full-year domestic aviation reading.",
        "refs": [
          "quarterly.q2.domAviationCAAC",
          "quarterly.q2.domAviationBig3",
          "quarterly.q1.domAviationCAAC",
          "quarterly.q1.domAviationBig3"
        ]
      },
      {
        "tag": "risk",
        "title": "Q2 international capacity gap widens to -14.0%",
        "body": "Q2 international flight capacity was <span class=\"num-highlight\">-14.0%</span> versus 2019 against -9.6% in Q1, the gap widening 4.4pp; international passenger growth slowed from +10.3% in Q1 to <span class=\"num-highlight\">+2.7%</span>, and from +12.8% to +1.2% for the Big 3. Capacity restoration did not keep pace with the first quarter's momentum. The pace of added flights in Q3 will decide whether the gap keeps widening.",
        "refs": [
          "quarterly.q2.intlCapacity",
          "quarterly.q1.intlCapacity",
          "quarterly.q2.intlAviationCAAC",
          "quarterly.q1.intlAviationCAAC",
          "quarterly.q2.intlAviationBig3",
          "quarterly.q1.intlAviationBig3"
        ]
      },
      {
        "tag": "outlook",
        "title": "Can domestic aviation return to growth in Q3",
        "body": "The third quarter covers the entire summer season, the most concentrated stretch of domestic travel demand in the year. The questions are whether domestic aviation can shake off the second quarter's contraction, whether hotel RevPAR can stay positive with occupancy falling, and whether the international capacity gap keeps widening. Whether peak-season strength offsets the second-quarter drag is the main variable for the full-year reading.",
        "refs": [
          "quarterly.q2.domAviationCAAC",
          "quarterly.q2.hotelRevPAR",
          "quarterly.q2.intlCapacity"
        ]
      }
    ]
  }
};
