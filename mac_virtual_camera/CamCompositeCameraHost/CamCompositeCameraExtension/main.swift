//
//  main.swift
//  CamCompositeCameraExtension
//
//  Created by Ashish Karigar on 7/7/26.
//

import Foundation
import CoreMediaIO

let providerSource = CamCompositeCameraExtensionProviderSource(clientQueue: nil)
CMIOExtensionProvider.startService(provider: providerSource.provider)

CFRunLoopRun()
