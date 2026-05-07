import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'category',
      label: 'Getting Started',
      customProps: {icon: 'IconRocket'},
      items: [
        'getting-started/overview',
        'getting-started/installation',
        'getting-started/quickstart',
      ],
    },
    {
      type: 'category',
      label: 'Configuration',
      customProps: {icon: 'IconBook'},
      items: [
        'configuration/providers',
        'configuration/environment-variables',
        'configuration/connect-your-target',
        'configuration/defining-rubrics',
        'configuration/creating-evaluation-set',
        'configuration/scoring-and-judges',
        'configuration/error-analysis',
      ],
    },
  ],
};

export default sidebars;
