# CSEE 4119 Spring 2026, Assignment 1 Testing File
## Your name: Alexander Qi

I tested the bunny test case w/ video playing, it opened up a new window then played all the video chunks in sequence  from ranging qualities. I initially tested the original sample bw.txt, the quality was low in the beginning due to the bw and then increased as the bw increased.

I played it again with a new bw.txt file with all high bandwith numbers, and the video quality was extremely consistent with the highest quality.

I tested with a high latency of 0.5 seconds to simulate a slow connection. Even though the bw.txt had decent bandwidth numbers, the latency bottlenecked everything and the client stuck to the lowest bitrate for most of the video. The log showed throughput estimates were consistently low since each recv took at least 0.5s regardless of the bandwidth.

I ran the same bw.txt twice with different alpha values, 0.1 and 0.9. With alpha 0.1 the throughput estimate changed slowly so the client was conservative about switching bitrates, it lagged behind the actual bandwidth changes. With alpha 0.9 it reacted almost immediately to bandwidth shifts and jumped to higher bitrates faster, but also dropped quality faster when bandwidth dipped.