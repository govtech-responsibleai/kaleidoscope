import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Kaleidoscope',
  tagline: 'Automated evaluation platform for AI-powered applications',
  favicon: 'img/favicon.ico',

  // future: {
  //   v4: true,
  // },

  url: 'https://govtech-responsibleai.github.io',
  baseUrl: '/kaleidoscope/',

  organizationName: 'govtech-responsibleai',
  projectName: 'kaleidoscope',

  onBrokenLinks: 'throw',
  trailingSlash: true,

  headTags: [
    {
      tagName: 'meta',
      attributes: {
        name: 'algolia-site-verification',
        content: '498DC7D7776A944B',
      },
    },
  ],

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl:
            'https://github.com/govtech-responsibleai/kaleidoscope/tree/main/docs/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/social-card.png',
    colorMode: {
      defaultMode: 'light',
      respectPrefersColorScheme: false,
    },
    algolia: {
      appId: 'C371UDORVB',
      apiKey: 'd13336baa469fbe00dfd7d60db59ceba',
      indexName: 'kaleidoscope_docs_pages',
      contextualSearch: true,
      searchPagePath: false,
    },
    navbar: {
      items: [
        {
          type: 'html',
          position: 'left',
          value: `<a href="/kaleidoscope/" class="navbar-lockup">
            <img src="/kaleidoscope/img/kaleidoscope-logo-text-2.png" alt="Project Kaleidoscope — Powered by GovTech Singapore" class="navbar-lockup-logo navbar-lockup-logo--light" />
            <img src="/kaleidoscope/img/kaleidoscope-logo-text-2-light.png" alt="Project Kaleidoscope — Powered by GovTech Singapore" class="navbar-lockup-logo navbar-lockup-logo--dark" />
          </a>`,
        },
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'right',
          label: 'Docs',
        },
        {
          href: 'https://blog.ai.gov.sg/building-an-automated-evals-workflow-that-works-and-open-sourcing-it/',
          label: 'Blog',
          position: 'right',
        },
        {
          href: 'https://github.com/govtech-responsibleai/kaleidoscope',
          position: 'right',
          className: 'header-github-link',
          'aria-label': 'GitHub repository',
        },
        {
          type: 'search',
          position: 'right',
        },
        {
          href: 'https://eval.ai-platform.string.sg/',
          label: 'WOG? Find out more.',
          position: 'right',
          className: 'navbar-cta-button',
        },
      ],
    },
    footer: {
      links: [
        {
          title: 'Docs',
          items: [
            { label: 'Getting Started', to: '/docs/getting-started/quickstart' },
            { label: 'Configuration', to: '/docs/configuration/connect-your-target' },
          ],
        },
        {
          title: 'Community',
          items: [
            { label: 'Blog', href: '#' },
            { label: 'GitHub', href: 'https://github.com/govtech-responsibleai/kaleidoscope' },
          ],
        },
        {
          title: 'More',
          items: [
            { label: 'WOG? Find out more', href: 'https://eval.ai-platform.string.sg/' },
          ],
        },
      ],
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
