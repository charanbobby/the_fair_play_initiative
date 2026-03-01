/**
 * App Layout Template
 * 
 * Defines the main structure for the application.
 */

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang=\"en\">
      <body>{children}</body>
    </html>
  );
}
