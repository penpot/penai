# Penpot Plugin Starter Template

This repository is designed to be your starting point for creating plugins for Penpot. Follow these instructions to set up your development environment and start building your own Penpot plugins.

## Getting Started

### Clone the Repository

Begin by cloning this repository to your local machine. Use the following command in your terminal:

```bash
git clone --depth 1 https://github.com/penpot/penpot-plugin-starter-template penpot-plugin
```

This command clones the latest version of the template into a folder named `penpot-plugin`.

### Configure the Plugin

Next, you need to edit the plugin's configuration file:

1. Navigate to the `penpot-plugin` directory.
2. Open the `manifest.json` file located in the `/public` folder.
3. Make any necessary changes to the configuration. Note that any modifications to this file require you to restart the development server for changes to take effect.

### Run the Development Server

To start the development server, run the following command in your terminal:

```bash
npm run dev
```

Once the server is running, open your web browser and go to `http://localhost:4400` to view your plugin in action. Now is ready to be loaded in Penpot.

## Development

### Technologies Used

This plugin template uses several key technologies:

- **TypeScript**
- **Vite**
- **Web Components**

### Libraries Included

The template includes two Penpot libraries to assist in your development:

- `@penpot/plugin-styles`: This library provides utility functions and resources to help you style your components consistently with Penpot's design system.
- `@penpot/plugin-types`: This library includes types and API descriptions for interacting with the Penpot plugin API, facilitating the development of plugins that can communicate effectively with the Penpot app.

## Build Your Plugin

When you're ready to build your plugin for production, run the following command:

```bash
npm run build
```

This command compiles your TypeScript code and assets into JavaScript, creating a `dist` folder that contains all the files necessary to deploy your plugin.
