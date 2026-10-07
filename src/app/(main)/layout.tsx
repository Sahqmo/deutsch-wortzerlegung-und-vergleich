import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "독일어 합성어 상성 진단소",
  description: "독일어 합성어를 블록으로 쪼개고, 영어·한국어·일본어 중 누가 가장 비슷하게 만들었는지 퍼센트로 판정해요.",
  openGraph: {
    title: "독일어 합성어 상성 진단소",
    description: "이 독일어 단어, 우리말이랑 얼마나 닮았을까? 짜임 궁합 테스트",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f3ee" },
    { media: "(prefers-color-scheme: dark)", color: "#111216" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&family=Noto+Sans+KR:wght@400;500;700;800&display=swap"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
