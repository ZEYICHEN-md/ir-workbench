// ============================================================
// 旅游看板洞察投影 — 请勿手改
// 权威：data/canonical/travel-insights.json
// 重新生成：ir industry generate-dashboard
// ============================================================

const INSIGHTS = {
  "meta": {
    "basedOnTravelJsonUpdatedAt": "2026-08-08",
    "confirmedAt": {
      "weekly": "2026-08-17",
      "monthly": "2026-08-17",
      "quarterly": "2026-08-17"
    },
    "stale": {
      "weekly": true,
      "monthly": true,
      "quarterly": true
    }
  },
  "weekly": {
    "zh": [
      {
        "tag": "highlight",
        "title": "客运量连续四周同比转正",
        "body": "8/2-8/8 国内航空客运量同比 <span class=\"num-highlight\">+4.0%</span>，为连续第四周转正，但较前一周 +8.0% 回落，客运航班量同比 <span class=\"num-highlight\">+2.0%</span>。暑运下半程客流仍在，同比弹性已从 7 月末高点回落。",
        "refs": [
          "weekly.aviationPax@7/19-7/25",
          "weekly.aviationPax@7/26-8/1",
          "weekly.aviationPax@8/2-8/8",
          "weekly.aviationFlight@8/2-8/8"
        ]
      },
      {
        "tag": "risk",
        "title": "量强价弱未破，票价同比 -8%",
        "body": "8/2-8/8 机票票价同比 <span class=\"num-highlight\">-8.0%</span>，较前一周 -7.0% 再走弱，客运量走强未能带动收益。运力供给充足、旅客价格敏感，叠加 8 月 5 日起燃油附加费再下调，含税票价同比继续承压。",
        "refs": [
          "weekly.aviationTicket@7/26-8/1",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.aviationPax@8/2-8/8"
        ]
      },
      {
        "tag": "risk",
        "title": "酒店 RevPAR 收窄中断",
        "body": "8/2-8/8 酒店 RevPAR 同比 <span class=\"num-highlight\">-1.5%</span>，较前一周 -0.9% 重新走阔（入住率 <span class=\"num-highlight\">-1.6%</span>、ADR 近乎持平）。此前连续三周收窄的通道被打断，量价转正仍未兑现。",
        "refs": [
          "weekly.hotelRevPAR@7/19-7/25",
          "weekly.hotelRevPAR@7/26-8/1",
          "weekly.hotelRevPAR@8/2-8/8",
          "weekly.hotelOccupancy@8/2-8/8",
          "weekly.hotelADR@8/2-8/8"
        ]
      },
      {
        "tag": "outlook",
        "title": "8 月中下旬量价能否重新收敛",
        "body": "后续看客运同比能否稳住、票价降幅会否收窄、酒店 RevPAR 能否重回收窄；若量回落而价仍弱，暑运收益改善空间更窄。",
        "refs": [
          "weekly.aviationPax@8/2-8/8",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.hotelRevPAR@8/2-8/8"
        ]
      }
    ],
    "en": [
      {
        "tag": "highlight",
        "title": "Pax positive four straight weeks",
        "body": "8/2–8/8 domestic air pax was <span class=\"num-highlight\">+4.0%</span> YoY, a fourth straight positive week, but down from +8.0% the prior week, with flights about <span class=\"num-highlight\">+2.0%</span>. Summer traffic is still there; YoY momentum has cooled from the late-July high.",
        "refs": [
          "weekly.aviationPax@7/19-7/25",
          "weekly.aviationPax@7/26-8/1",
          "weekly.aviationPax@8/2-8/8",
          "weekly.aviationFlight@8/2-8/8"
        ]
      },
      {
        "tag": "risk",
        "title": "Volume-up, price-down intact; fares -8%",
        "body": "8/2–8/8 airfares were <span class=\"num-highlight\">-8.0%</span> YoY, weaker than -7.0% the prior week — stronger pax did not lift yields. Ample capacity and price-sensitive travelers, plus the Aug 5 fuel-surcharge cut, kept inclusive fares under YoY pressure.",
        "refs": [
          "weekly.aviationTicket@7/26-8/1",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.aviationPax@8/2-8/8"
        ]
      },
      {
        "tag": "risk",
        "title": "Hotel RevPAR narrowing stalled",
        "body": "8/2–8/8 hotel RevPAR was <span class=\"num-highlight\">-1.5%</span> YoY, widening from -0.9% the prior week (occupancy <span class=\"num-highlight\">-1.6%</span>, ADR nearly flat). The three-week narrowing run broke; a turn to positive is still unproven.",
        "refs": [
          "weekly.hotelRevPAR@7/19-7/25",
          "weekly.hotelRevPAR@7/26-8/1",
          "weekly.hotelRevPAR@8/2-8/8",
          "weekly.hotelOccupancy@8/2-8/8",
          "weekly.hotelADR@8/2-8/8"
        ]
      },
      {
        "tag": "outlook",
        "title": "Can mid/late August re-converge volume and price",
        "body": "Watch whether pax YoY holds, fare declines narrow, and hotel RevPAR resumes tightening. If traffic cools while prices stay weak, summer yield repair has even less room.",
        "refs": [
          "weekly.aviationPax@8/2-8/8",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.hotelRevPAR@8/2-8/8"
        ]
      }
    ]
  },
  "monthly": {
    "zh": [
      {
        "tag": "risk",
        "title": "6 月国内航空仍深度走弱",
        "body": "最近一期完整月度（6 月）民航局口径国内航空同比 <span class=\"num-highlight\">-7.1%</span>、三大航约 <span class=\"num-highlight\">-7.8%</span>。Q2 高油价压成本、航司控运力是主因；7 月月度尚未落地，周度客运已转正，能否在月度兑现仍待验证。",
        "refs": [
          "monthly.domAviationCAAC@6月",
          "monthly.domAviationBig3@6月"
        ]
      },
      {
        "tag": "risk",
        "title": "国际运力相对 2019 缺口仍深",
        "body": "6 月国际运力（vs 2019）同比 <span class=\"num-highlight\">-16.3%</span>，国际客运量约 <span class=\"num-highlight\">-2.0%</span>。缺口持续存在，恢复偏慢；关注国际增班与入境需求转化。",
        "refs": [
          "monthly.intlCapacity@6月",
          "monthly.intlAviationCAAC@6月"
        ]
      },
      {
        "tag": "outlook",
        "title": "7 月月度待出，周度量价尚未同步",
        "body": "6 月酒店入住率同比 <span class=\"num-highlight\">-2.5%</span>、ADR <span class=\"num-highlight\">+2.2%</span>，量缩价稳；对照当前周度 8/2-8/8，客运量同比 <span class=\"num-highlight\">+4.0%</span>、票价 -8.0%、酒店 RevPAR -1.5%。7 月月度将验证暑期改善能否在月度落地。",
        "refs": [
          "monthly.hotelOccupancy@6月",
          "monthly.hotelADR@6月",
          "weekly.aviationPax@8/2-8/8",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.hotelRevPAR@8/2-8/8"
        ]
      }
    ],
    "en": [
      {
        "tag": "risk",
        "title": "June domestic air still deeply negative",
        "body": "The latest complete month (June) CAAC domestic pax was <span class=\"num-highlight\">-7.1%</span> YoY, Big3 about <span class=\"num-highlight\">-7.8%</span>. Q2 high fuel and capacity cuts were the main drivers; July monthly is still out, while weekly pax has already turned positive — whether that prints at month level is unproven.",
        "refs": [
          "monthly.domAviationCAAC@6月",
          "monthly.domAviationBig3@6月"
        ]
      },
      {
        "tag": "risk",
        "title": "Intl capacity gap vs 2019 still wide",
        "body": "June capacity vs 2019 was <span class=\"num-highlight\">-16.3%</span> YoY; intl pax about <span class=\"num-highlight\">-2.0%</span>. The shortfall persists; watch intl add-backs and inbound demand conversion.",
        "refs": [
          "monthly.intlCapacity@6月",
          "monthly.intlAviationCAAC@6月"
        ]
      },
      {
        "tag": "outlook",
        "title": "July monthly pending; weekly volume and price still diverge",
        "body": "June hotels were volume-down, price-stable (occupancy <span class=\"num-highlight\">-2.5%</span>, ADR <span class=\"num-highlight\">+2.2%</span>); against that, 8/2–8/8 pax is +4.0% YoY, fares -8.0%, hotel RevPAR -1.5%. July monthly will show whether summer improvement lands at month level.",
        "refs": [
          "monthly.hotelOccupancy@6月",
          "monthly.hotelADR@6月",
          "weekly.aviationPax@8/2-8/8",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.hotelRevPAR@8/2-8/8"
        ]
      }
    ]
  },
  "quarterly": {
    "zh": [
      {
        "tag": "risk",
        "title": "Q2 国内航转负，铁路仍稳",
        "body": "Q2 国内航空同比约 <span class=\"num-highlight\">-5.2%</span>、三大航约 <span class=\"num-highlight\">-6.0%</span>；铁路仍 <span class=\"num-highlight\">+4.6%</span>，难对冲航空转负。Q2 高油价叠加快季末淡季，航司收缩运力是主因。",
        "refs": [
          "quarterly.q2.domAviationCAAC",
          "quarterly.q2.domAviationBig3",
          "quarterly.q2.railway"
        ]
      },
      {
        "tag": "outlook",
        "title": "Q3 中期量价仍未同步修复",
        "body": "Q3 已过半，8/2-8/8 周度客运量同比 <span class=\"num-highlight\">+4.0%</span>、酒店 RevPAR <span class=\"num-highlight\">-1.5%</span>，票价同比仍 <span class=\"num-highlight\">-8.0%</span>。量已转正、价与酒店仍弱，不宜由单周回暖外推全季。",
        "refs": [
          "weekly.aviationPax@8/2-8/8",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.hotelRevPAR@8/2-8/8",
          "quarterly.q2.domAviationCAAC"
        ]
      }
    ],
    "en": [
      {
        "tag": "risk",
        "title": "Q2 domestic air turned negative; railway held up",
        "body": "Q2 domestic air was about <span class=\"num-highlight\">-5.2%</span> YoY with Big3 about <span class=\"num-highlight\">-6.0%</span>; railway still <span class=\"num-highlight\">+4.6%</span>, not enough to offset the air swing. Q2 high fuel plus late-season softness drove capacity cuts.",
        "refs": [
          "quarterly.q2.domAviationCAAC",
          "quarterly.q2.domAviationBig3",
          "quarterly.q2.railway"
        ]
      },
      {
        "tag": "outlook",
        "title": "Q3 mid-term: volume and price still not repairing together",
        "body": "Past the halfway mark of Q3, 8/2–8/8 weekly pax is <span class=\"num-highlight\">+4.0%</span> YoY and hotel RevPAR <span class=\"num-highlight\">-1.5%</span>, with fares still <span class=\"num-highlight\">-8.0%</span>. Volume is positive; fares and hotels remain weak — a few warm weeks do not extrapolate to a full quarter.",
        "refs": [
          "weekly.aviationPax@8/2-8/8",
          "weekly.aviationTicket@8/2-8/8",
          "weekly.hotelRevPAR@8/2-8/8",
          "quarterly.q2.domAviationCAAC"
        ]
      }
    ]
  }
};
