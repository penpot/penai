# Penpot AI Plugins

This folder contains the code for exemplary AI Penpot plugins.

## Usage

### Run the Development Server

To start the development server, run the following command in your terminal:

```bash
npm run dev
```

Once the server is running, open your web browser and go to `http://localhost:4400` to view your plugin in action. Now is ready to be loaded in Penpot.

## Development

### Test on remote Penpot instance

It is recommended to develop and test Penpot plugins on a local Penpot instance. See the [self-host docs](https://penpot.app/self-host) for more information.

However, if a local deployment is not viable or a plugin has to be tested with a remote Penpot instance, we recommend to use a reverse proxy such as ngrok or telebit to make the local development build accessible on the internet.

For instance, after telebit is configured, use the following command to expose the local port 4400 to the internet:

```bash
$ telebit http 4400
> Forwarding https://<jondoe>.telebit.io => localhost:3000
```




### Technologies Used

This plugin template uses several key technologies:

- **TypeScript**
- **Vite**
- **Web Components**